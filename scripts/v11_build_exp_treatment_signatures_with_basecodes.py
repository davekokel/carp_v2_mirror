#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import csv
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

SHEET = "seed_kits/legacy_wrangling_v3/working/imaging_sheet_augmented_v3.csv"
ROI_CSV = "seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9_compat.csv"

OUT_OK = "seed_kits/legacy_wrangling_v3/working/exp_treatment_signatures.csv"
OUT_BAD = "seed_kits/legacy_wrangling_v3/working/exp_treatment_signatures_ambiguous.csv"

OUT_TOKEN_MAP = "seed_kits/legacy_wrangling_v3/working/exp_treatment_token_map.csv"

RE_SHEET = re.compile(r"(Aang_Foundation|Korra_Foundation|Exploratory_fish)[/\\](\d{8}[^/\\]+)", re.I)
RE_ROI = re.compile(r"/(Aang_Foundation|Korra_Foundation|Exploratory_fish)/(\d{8}[^/]+)/", re.I)

RE_MGCO = re.compile(r"\bmgco\s*-?\s*0*([0-9]+)\b", re.I)
RE_PDQM = re.compile(r"\bpdqm\s*-?\s*0*([0-9]+)\b", re.I)
RE_HC   = re.compile(r"\bhc\s*-?\s*0*([0-9]+)\b", re.I)

RE_WS = re.compile(r"\s+")

def _s(x) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return ""
    v = str(x).strip()
    if v.lower() in ("nan", "none"):
        return ""
    return v

def _canon_foundation(name: str) -> str:
    n = _s(name)
    lo = n.lower()
    if lo == "aang_foundation":
        return "Aang_Foundation"
    if lo == "korra_foundation":
        return "Korra_Foundation"
    if lo == "exploratory_fish":
        return "Exploratory_fish"
    return n

def key_from_sheet(path: str) -> str:
    m = RE_SHEET.search(_s(path))
    if not m:
        return ""
    return f"{_canon_foundation(m.group(1))}/{m.group(2)}"

def key_from_roi_dir(path: str) -> str:
    p = _s(path).replace("\\", "/")
    m = RE_ROI.search(p)
    if not m:
        return ""
    return f"{_canon_foundation(m.group(1))}/{m.group(2)}"

def _strip_parens(s: str) -> str:
    return re.sub(r"\(.*?\)", "", s)

def _split_list_cell(cell: str) -> List[str]:
    """
    Split ONLY on explicit list separators. Do NOT split on spaces.
    """
    s = _s(cell)
    if not s:
        return []
    s = _strip_parens(s)
    s = s.replace("|", ",").replace(";", ",")
    s = s.replace("—", "-").replace("–", "-")
    s = RE_WS.sub(" ", s).strip()
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return parts


def _split_construct_cell(cell: str) -> List[str]:
    s = _s(cell)
    if not s:
        return []
    s = _strip_parens(s)
    s = s.replace('|', ',').replace(';', ',')
    s = s.replace('—', '-').replace('–', '-')
    s = RE_WS.sub(' ', s).strip()
    chunks = [c.strip() for c in s.split(',') if c.strip()]
    out: List[str] = []
    for chunk in chunks:
        for w in [x for x in re.split(r'\s+', chunk.strip()) if x]:
            out.append(w)
    return out

def _norm_token(raw: str) -> str:
    """
    Normalize to a stable token key (still human-ish, not basecode).
    This is ONLY for joining into token_map.
    """
    s = _s(raw).lower()
    if not s:
        return ""
    s = _strip_parens(s).strip()
    s = s.replace("—", "-").replace("–", "-")
    s = RE_WS.sub("", s)  # remove whitespace entirely for stability
    s = RE_MGCO.sub(r"mgco-\1", s)
    s = RE_PDQM.sub(r"pdqm-\1", s)
    s = RE_HC.sub(r"hc-\1", s)
    s = re.sub(r"\bmstaygold\b", "msg", s)
    s = re.sub(r"\btdmstaygold\b", "tdmsg", s)
    s = re.sub(r"\bjf\s*-?\s*0*635\b", "jf-635", s)
    return s

def _ing_sig(tokens: List[str]) -> str:
    return ",".join(sorted(set([t for t in tokens if t])))

def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    df_sheet = pd.read_csv(SHEET, low_memory=False)
    df_sheet.columns = [str(c).strip() for c in df_sheet.columns]
    for col in ("Data location", "additional plasmids injected", "additional mRNAs injected", "additonal dye and chemicals"):
        if col not in df_sheet.columns:
            raise SystemExit(f"[STOP] missing column in sheet CSV: {col!r}")

    df_sheet["dataset_key"] = df_sheet["Data location"].map(key_from_sheet)
    df_sheet = df_sheet[df_sheet["dataset_key"] != ""].copy()

    df_sheet["pla_raw"] = df_sheet["additional plasmids injected"].map(_split_construct_cell)
    df_sheet["rna_raw"] = df_sheet["additional mRNAs injected"].map(_split_construct_cell)
    df_sheet["dye_raw"] = df_sheet["additonal dye and chemicals"].map(_split_list_cell)

    df_sheet["pla_tok"] = df_sheet["pla_raw"].map(lambda xs: [_norm_token(x) for x in xs])
    df_sheet["rna_tok"] = df_sheet["rna_raw"].map(lambda xs: [_norm_token(x) for x in xs])
    df_sheet["dye_tok"] = df_sheet["dye_raw"].map(lambda xs: [_norm_token(x) for x in xs])

    df_sheet["signature_tokens"] = df_sheet.apply(
        lambda r: f"plasmids={_ing_sig(r.pla_tok)}|rnas={_ing_sig(r.rna_tok)}|dyes={_ing_sig(r.dye_tok)}",
        axis=1,
    )

    sig_counts = df_sheet.groupby("dataset_key")["signature_tokens"].nunique().reset_index(name="n_signatures")
    bad_keys = set(sig_counts.loc[sig_counts["n_signatures"] > 1, "dataset_key"].astype(str).tolist())

    df_roi = pd.read_csv(ROI_CSV, low_memory=False)
    df_roi.columns = [str(c).strip() for c in df_roi.columns]
    if "roi_dir" not in df_roi.columns or "bruker_roi_id" not in df_roi.columns:
        raise SystemExit("[STOP] ROI compat CSV missing roi_dir or bruker_roi_id")

    df_roi["dataset_key"] = df_roi["roi_dir"].map(key_from_roi_dir)
    df_roi = df_roi[df_roi["dataset_key"] != ""].copy()
    df_roi["bruker_roi_id"] = df_roi["bruker_roi_id"].astype(str).str.strip()

    df_units = df_sheet[["dataset_key", "signature_tokens"]].drop_duplicates()
    df_join = df_roi[["bruker_roi_id", "dataset_key"]].merge(df_units, on="dataset_key", how="inner").drop_duplicates()

    df_bad = df_join[df_join["dataset_key"].isin(bad_keys)].sort_values(["dataset_key", "bruker_roi_id", "signature_tokens"]).reset_index(drop=True)
    df_ok  = df_join[~df_join["dataset_key"].isin(bad_keys)].sort_values(["dataset_key", "bruker_roi_id"]).reset_index(drop=True)

    # Write OK/BAD with BOTH signatures: raw token signature and canonical-basecode signature (filled later via token_map)
    df_ok = df_ok.rename(columns={"signature_tokens": "signature_tokens"})
    df_ok["signature_basecodes"] = ""  # filled by token_map pass
    df_ok.to_csv(OUT_OK, index=False)

    df_bad = df_bad.rename(columns={"signature_tokens": "signature_tokens"})
    df_bad["signature_basecodes"] = ""
    df_bad.to_csv(OUT_BAD, index=False)

    # Build token_map skeleton (unique tokens across OK rows)
    toks = set()
    for s in df_ok["signature_tokens"].astype(str).tolist():
        m = re.search(r"plasmids=([^|]*)\|rnas=([^|]*)\|dyes=([^|]*)", s)
        if not m:
            continue
        for blob in (m.group(1), m.group(2), m.group(3)):
            for t in [x.strip() for x in blob.split(",") if x.strip()]:
                toks.add(t)

    eng = create_engine(db_url)
    with eng.begin() as cx:
        # construct aliases
        c_rows = cx.execute(
            text(
                """
                SELECT lower(c.base_code) AS base_code, lower(a.alias) AS alias
                FROM public.construct_aliases a
                JOIN public.constructs c ON c.id = a.construct_id
                """
            )
        ).fetchall()
        alias_to_base: Dict[str, str] = { _s(alias): _s(base) for (base, alias) in c_rows if _s(alias) and _s(base) }

        # dyes (match by alnum key)
        d_rows = cx.execute(
            text(
                """
                SELECT lower(code) AS code,
                       lower(coalesce(nickname,'')) AS nickname,
                       lower(coalesce(display_name,'')) AS display_name
                FROM public.dyes
                """
            )
        ).fetchall()
        dye_key_to_code: Dict[str, str] = {}
        for code, nickname, display_name in d_rows:
            cc = _s(code)
            if not cc:
                continue
            for v in (cc, _s(nickname), _s(display_name)):
                k = re.sub(r"[^a-z0-9]+", "", v)
                if k:
                    dye_key_to_code[k] = cc

    rows = []
    for t in sorted(toks):
        kind = "construct"
        mapped = ""
        notes = ""
        if t.startswith("jf") or t.startswith("dye") or t == "635":
            kind = "dye"

        if kind == "construct":
            mapped = alias_to_base.get(t, "")
        else:
            k = re.sub(r"[^a-z0-9]+", "", t)
            mapped = dye_key_to_code.get(k, "")

        rows.append(
            {
                "token": t,
                "kind": kind,
                "mapped_code": mapped,  # fill this manually when blank
                "notes": notes,
            }
        )

    pd.DataFrame(rows).to_csv(OUT_TOKEN_MAP, index=False)

    print("WROTE_OK", OUT_OK, "rows", len(df_ok), "dataset_keys", df_ok["dataset_key"].nunique())
    print("WROTE_BAD", OUT_BAD, "rows", len(df_bad), "dataset_keys", df_bad["dataset_key"].nunique())
    print("WROTE_TOKEN_MAP", OUT_TOKEN_MAP, "rows", len(rows))

if __name__ == "__main__":
    main()
