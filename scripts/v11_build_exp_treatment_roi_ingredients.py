#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

SHEET_CSV = "seed_kits/legacy_wrangling_v3/working/imaging_sheet_augmented_v3.csv"
ROI_COMPAT_CSV = "seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9_compat.csv"

OUT_ROI_CONSTRUCTS = "seed_kits/legacy_wrangling_v3/working/exp_treatment_roi_constructs.csv"
OUT_ROI_DYES = "seed_kits/legacy_wrangling_v3/working/exp_treatment_roi_dyes.csv"
OUT_AMBIG = "seed_kits/legacy_wrangling_v3/working/qc_exp_treatment_ambiguous_datasets.csv"
OUT_UNKNOWN = "seed_kits/legacy_wrangling_v3/working/qc_exp_treatment_unknown_tokens.csv"

RE_DATASET = re.compile(r"(Aang_Foundation|Korra_Foundation|Exploratory_fish)[/\\](\d{8}[^/\\]+)", re.I)
RE_ROI_DIR = re.compile(r"/(Aang_Foundation|Korra_Foundation|Exploratory_fish)/(\d{8}[^/]+)/", re.I)

RE_MGCO_NODASH = re.compile(r"\bmgco0*([0-9]+)\b", re.I)
RE_MGCO_DASH = re.compile(r"\bmgco-0*([0-9]+)\b", re.I)
RE_PDQM_NODASH = re.compile(r"\bpdqm0*([0-9]+)\b", re.I)
RE_PDQM_DASH = re.compile(r"\bpdqm-0*([0-9]+)\b", re.I)


def _s(x) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none"):
        return ""
    return s


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


def _path_norm(p: str) -> str:
    p = _s(p)
    if not p:
        return ""
    p = p.replace("\\", "/")
    p = re.sub(r"/{2,}", "/", p)
    return p


def dataset_key_from_sheet_data_location(path: str) -> str:
    p = _path_norm(path)
    m = RE_DATASET.search(p)
    if not m:
        return ""
    return f"{_canon_foundation(m.group(1))}/{m.group(2)}"


def dataset_key_from_roi_dir(path: str) -> str:
    p = _path_norm(path)
    m = RE_ROI_DIR.search(p)
    if not m:
        return ""
    return f"{_canon_foundation(m.group(1))}/{m.group(2)}"


def _norm_construct_token(tok: str) -> str:
    t0 = _s(tok).lower()
    if not t0:
        return ""

    t = re.sub(r"\(.*?\)", "", t0).strip()
    t = t.replace("—", "-").replace("–", "-")
    t = re.sub(r"\s+", "", t)

    m = re.search(r"(mgco-?0*[0-9]+|pdqm-?0*[0-9]+|hc-?0*[0-9]+)", t, flags=re.I)
    if not m:
        return ""

    b = m.group(1).lower()
    b = re.sub(r"\s+", "", b)

    b = RE_MGCO_DASH.sub(r"mgco-\1", b)
    b = RE_MGCO_NODASH.sub(r"mgco-\1", b)
    b = RE_PDQM_DASH.sub(r"pdqm-\1", b)
    b = RE_PDQM_NODASH.sub(r"pdqm-\1", b)
    b = re.sub(r"\bhc-?0*([0-9]+)\b", r"hc-\1", b)

    return b

def _split_construct_tokens(cell: str) -> List[str]:
    """
    Parse construct tokens from the imaging sheet columns.

    Key rule: DO NOT split on spaces. Humans write tokens like:
      - "MGCO-01( ... )"
      - "2xCox8A:mSG"
      - "ef1a-extended:Halo:sec61b"
    and spaces should not create new tokens.

    We split only on explicit list separators: comma / semicolon / pipe.
    """
    s = _s(cell)
    if not s:
        return []

    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("|", ",").replace(";", ",")
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\s+", " ", s).strip()

    parts = [p.strip() for p in s.split(",") if p.strip()]

    out: List[str] = []
    seen = set()
    for p in parts:
        t = _norm_construct_token(p)
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _norm_dye_token(tok: str) -> str:
    t = _s(tok).lower()
    if not t:
        return ""
    t = re.sub(r"\(.*?\)", "", t).strip()
    t = t.replace("—", "-").replace("–", "-")

    # keep "jf 635" together -> "jf-635"
    t = re.sub(r"\s+", "-", t).strip("-")
    t = re.sub(r"-{2,}", "-", t)
    return t


def _split_dye_tokens(cell: str) -> List[str]:
    """
    Parse dyes from imaging sheet. DO NOT split on spaces.
    "JF 635" should remain a single token and normalize to "jf-635".
    """
    s = _s(cell)
    if not s:
        return []
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("|", ",").replace(";", ",")
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\s+", " ", s).strip()

    parts = [p.strip() for p in s.split(",") if p.strip()]

    out: List[str] = []
    seen = set()
    for p in parts:
        t = _norm_dye_token(p)
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _alnum_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _s(s).lower())


@dataclass(frozen=True)
class IngredientSet:
    plasmids: Tuple[str, ...]
    rnas: Tuple[str, ...]
    dyes: Tuple[str, ...]


def _ing_set(plasmids: List[str], rnas: List[str], dyes: List[str]) -> IngredientSet:
    return IngredientSet(tuple(sorted(set(plasmids))), tuple(sorted(set(rnas))), tuple(sorted(set(dyes))))


def _fluor_token_from_fusion_fluor(fluor: str) -> str:
    f = _s(fluor).lower()
    # normalize common fluor labels seen in fusion_pretty
    if f in ("mstaygold", "msg"):
        return "msg"
    if f in ("tdmstaygold", "tdmsg"):
        return "tdmsg"
    if f in ("halo",):
        return "halo"
    if f in ("tdmchilada", "mchilada", "chilada"):
        return "mchilada"
    if f in (
        "tdmscarlet3s2",
        "mscarlet3s2",
        "tdmscarlet3",
        "mscarlet3",
        "mscarlet3-s2",
        "tdmscarlet3-s2",
    ):
        # canonical token used in unknown list often includes "-s2"
        return "mscarlet3-s2"
    return ""


def _target_token_from_fusion_target(t: str) -> str:
    x = _s(t).lower()
    x = re.sub(r"\s+", "", x)
    x = x.replace("-", "").replace("_", "")
    return x


def _add_synthetic_aliases_from_fusions(cx, alias_to_base: Dict[str, str]) -> None:
    """
    Deterministic: derive alias forms like "msg:sec61b" from canonical fusion_pretty.

    If v_constructs_overview says:
      fusion_pretty = "mStayGold-sec61b(N)"
    then:
      msg:sec61b  -> construct_code (base_code in v_constructs_overview)
      sec61b:msg  -> construct_code
    """
    rows = cx.execute(
        text(
            """
            SELECT lower(construct_code) AS construct_code,
                   lower(coalesce(fusion_pretty,'')) AS fusion_pretty
            FROM public.v_constructs_overview
            WHERE coalesce(btrim(fusion_pretty),'') <> '';
            """
        )
    ).fetchall()

    fp_re = re.compile(r"^(?P<fluor>[a-z0-9]+)-(?P<target>[^()]+)\(", re.I)

    for construct_code, fusion_pretty in rows:
        bc = _s(construct_code).lower()
        fp = _s(fusion_pretty).lower()
        if not bc or not fp:
            continue

        m = fp_re.match(fp)
        if not m:
            continue

        fluor_tok = _fluor_token_from_fusion_fluor(m.group("fluor"))
        target_tok = _target_token_from_fusion_target(m.group("target"))
        if not fluor_tok or not target_tok:
            continue

        alias_to_base[f"{fluor_tok}:{target_tok}"] = bc
        alias_to_base[f"{target_tok}:{fluor_tok}"] = bc


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    # ── Load imaging sheet and compute per-dataset ingredient sets ────────────
    df_sheet = pd.read_csv(SHEET_CSV, low_memory=False)
    df_sheet.columns = [str(c).strip() for c in df_sheet.columns]

    for col in ("Data location", "additional plasmids injected", "additional mRNAs injected", "additonal dye and chemicals"):
        if col not in df_sheet.columns:
            raise SystemExit(f"[STOP] missing column in sheet CSV: {col!r}")

    df_sheet["dataset_key"] = df_sheet["Data location"].map(dataset_key_from_sheet_data_location)
    df_sheet = df_sheet[df_sheet["dataset_key"] != ""].copy()

    df_sheet["plasmid_tokens"] = df_sheet["additional plasmids injected"].map(_split_construct_tokens)
    df_sheet["rna_tokens"] = df_sheet["additional mRNAs injected"].map(_split_construct_tokens)
    df_sheet["dye_tokens"] = df_sheet["additonal dye and chemicals"].map(_split_dye_tokens)
    df_sheet["ing_set"] = df_sheet.apply(lambda r: _ing_set(r.plasmid_tokens, r.rna_tokens, r.dye_tokens), axis=1)

    set_counts = df_sheet.groupby("dataset_key")["ing_set"].nunique().reset_index(name="n_sets")
    bad_keys = set(set_counts.loc[set_counts["n_sets"] > 1, "dataset_key"].astype(str).tolist())

    # ── Write ambiguous datasets report (hashable; no lists in dedupe) ────────
    amb_rows: List[Dict[str, str]] = []
    if bad_keys:
        for dk in sorted(bad_keys):
            sub = df_sheet[df_sheet["dataset_key"] == dk].copy()

            sub["plasmids_s"] = sub["plasmid_tokens"].map(lambda xs: ",".join(xs or []))
            sub["rnas_s"] = sub["rna_tokens"].map(lambda xs: ",".join(xs or []))
            sub["dyes_s"] = sub["dye_tokens"].map(lambda xs: ",".join(xs or []))

            sub["signature"] = sub.apply(
                lambda r: f"plasmids={r.plasmids_s}|rnas={r.rnas_s}|dyes={r.dyes_s}",
                axis=1,
            )

            sub = sub[["dataset_key", "signature", "plasmids_s", "rnas_s", "dyes_s"]].drop_duplicates()

            for rr in sub.itertuples(index=False):
                amb_rows.append(
                    {
                        "dataset_key": rr.dataset_key,
                        "signature": rr.signature,
                        "plasmids_raw": rr.plasmids_s,
                        "rnas_raw": rr.rnas_s,
                        "dyes_raw": rr.dyes_s,
                    }
                )

    pd.DataFrame(
        amb_rows,
        columns=["dataset_key", "signature", "plasmids_raw", "rnas_raw", "dyes_raw"],
    ).sort_values(["dataset_key", "signature"]).to_csv(OUT_AMBIG, index=False)

    # For non-ambiguous datasets, take the first (they should all match)
    df_ok = df_sheet[~df_sheet["dataset_key"].isin(bad_keys)].copy()
    df_units = (
        df_ok.groupby("dataset_key").first(numeric_only=False).reset_index()[
            ["dataset_key", "plasmid_tokens", "rna_tokens", "dye_tokens"]
        ]
    )

    # ── Build canonical resolution tables from DB ────────────────────────────
    eng = create_engine(db_url)
    with eng.begin() as cx:
        # construct alias → base_code (canonical)
        c_rows = cx.execute(
            text(
                """
                SELECT lower(c.base_code) AS base_code, lower(coalesce(a.alias,'')) AS alias
                FROM public.constructs c
                LEFT JOIN public.construct_aliases a ON a.construct_id = c.id;
                """
            )
        ).fetchall()

        alias_to_base: Dict[str, str] = {}
        for base_code, alias in c_rows:
            bc = _s(base_code).lower()
            al = _s(alias).lower()
            if bc:
                alias_to_base[_norm_construct_token(bc)] = bc
            if al:
                alias_to_base[_norm_construct_token(al)] = bc

        # add deterministic synthetic aliases from fusion_pretty
        _add_synthetic_aliases_from_fusions(cx, alias_to_base)

        # dyes: build flexible lookup by alnum key against code/display/nickname
        dye_rows = cx.execute(
            text(
                """
                SELECT lower(code) AS code,
                       lower(coalesce(nickname,'')) AS nickname,
                       lower(coalesce(display_name,'')) AS display_name
                FROM public.dyes;
                """
            )
        ).fetchall()

        dye_key_to_code: Dict[str, str] = {}
        for code, nickname, display_name in dye_rows:
            c = _s(code).lower()
            if c:
                dye_key_to_code[_alnum_key(c)] = c
            n = _s(nickname).lower()
            if n:
                dye_key_to_code[_alnum_key(n)] = c
            d = _s(display_name).lower()
            if d:
                dye_key_to_code[_alnum_key(d)] = c

    unknown_rows: List[Dict[str, str]] = []

    def resolve_construct(tok: str) -> str:
        t = _norm_construct_token(tok)
        if not t:
            return ""
        if t in alias_to_base:
            return alias_to_base[t]
        unknown_rows.append({"kind": "construct", "raw": _s(tok), "normalized": t})
        return ""

    def resolve_dye(tok: str) -> str:
        t = _norm_dye_token(tok)
        if not t:
            return ""
        k = _alnum_key(t)
        if k in dye_key_to_code:
            return dye_key_to_code[k]
        unknown_rows.append({"kind": "dye", "raw": _s(tok), "normalized": t})
        return ""

    # ── Load ROI compat file and fan-out units to ROI rows ───────────────────
    df_roi = pd.read_csv(ROI_COMPAT_CSV, low_memory=False)
    df_roi.columns = [str(c).strip() for c in df_roi.columns]
    if "roi_dir" not in df_roi.columns or "bruker_roi_id" not in df_roi.columns:
        raise SystemExit("[STOP] ROI compat CSV missing roi_dir or bruker_roi_id")

    df_roi["dataset_key"] = df_roi["roi_dir"].map(dataset_key_from_roi_dir)
    df_roi = df_roi[df_roi["dataset_key"] != ""].copy()
    df_roi["bruker_roi_id"] = df_roi["bruker_roi_id"].astype(str).str.strip()

    df_join = df_roi[["bruker_roi_id", "dataset_key"]].merge(df_units, on="dataset_key", how="inner")

    roi_construct_rows: List[Dict[str, str]] = []
    roi_dye_rows: List[Dict[str, str]] = []

    for r in df_join.itertuples(index=False):
        roi_code = _s(r.bruker_roi_id)
        dk = _s(r.dataset_key)

        for raw in list(r.plasmid_tokens or []):
            bc = resolve_construct(raw)
            if bc:
                roi_construct_rows.append(
                    {
                        "bruker_roi_id": roi_code,
                        "dataset_key": dk,
                        "delivery_form": "plasmid",
                        "construct_base_code": bc,
                    }
                )

        for raw in list(r.rna_tokens or []):
            bc = resolve_construct(raw)
            if bc:
                roi_construct_rows.append(
                    {
                        "bruker_roi_id": roi_code,
                        "dataset_key": dk,
                        "delivery_form": "rna",
                        "construct_base_code": bc,
                    }
                )

        for raw in list(r.dye_tokens or []):
            dc = resolve_dye(raw)
            if dc:
                roi_dye_rows.append({"bruker_roi_id": roi_code, "dataset_key": dk, "dye_code": dc})

    df_c = pd.DataFrame(roi_construct_rows).drop_duplicates().sort_values(
        ["dataset_key", "bruker_roi_id", "delivery_form", "construct_base_code"]
    )
    df_d = pd.DataFrame(roi_dye_rows).drop_duplicates().sort_values(["dataset_key", "bruker_roi_id", "dye_code"])

    df_c.to_csv(OUT_ROI_CONSTRUCTS, index=False)
    df_d.to_csv(OUT_ROI_DYES, index=False)

    if unknown_rows:
        pd.DataFrame(unknown_rows).drop_duplicates().sort_values(["kind", "normalized", "raw"]).to_csv(OUT_UNKNOWN, index=False)
        raise SystemExit(f"[STOP] unknown tokens found; see {OUT_UNKNOWN}")

    print("WROTE", OUT_ROI_CONSTRUCTS, "rows", len(df_c), "datasets", df_c["dataset_key"].nunique())
    print("WROTE", OUT_ROI_DYES, "rows", len(df_d), "datasets", df_d["dataset_key"].nunique())
    print("WROTE", OUT_AMBIG, "rows", (0 if not bad_keys else len(amb_rows)))
    print("BAD_DATASETS", len(bad_keys))


if __name__ == "__main__":
    main()