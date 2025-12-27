#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


TOKEN_SPLIT = re.compile(r"[|,; ]+")
BASECODE_RE = re.compile(r"^([A-Za-z]+)[-_ ]*0*([0-9]+)$")


def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")


def _canon_basecode(tok: str) -> Optional[str]:
    s = (tok or "").strip()
    if not s:
        return None
    s_l = s.lower()
    if s_l in ("nan", "none", "na", "n/a", "<na>"):
        return None
    m = BASECODE_RE.match(s)
    if not m:
        return s_l
    return f"{m.group(1).lower()}-{int(m.group(2))}"


def _split_tokens_pipe(raw: object) -> List[str]:
    if not _nonempty(raw):
        return []
    parts = [p.strip() for p in TOKEN_SPLIT.split(str(raw)) if p.strip()]
    out: List[str] = []
    for p in parts:
        c = _canon_basecode(p)
        if c:
            out.append(c)
    out = sorted(dict.fromkeys(out))
    return out


def _split_allele_tokens(raw: object) -> List[str]:
    if not _nonempty(raw):
        return []
    parts = [p.strip() for p in TOKEN_SPLIT.split(str(raw)) if p.strip()]
    out: List[str] = []
    for p in parts:
        s = str(p).strip()
        if not s:
            continue
        s_l = s.lower()
        if s_l in ("nan", "none", "na", "n/a", "<na>"):
            continue
        if s.endswith(".0") and s[:-2].isdigit():
            s = s[:-2]
        out.append(s)
    out = sorted(dict.fromkeys(out))
    return out


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"[STOP] CSV not found: {path}")
    df = pd.read_csv(path, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("[STOP] DB_URL must be set (needed to resolve allele tokens via public.transgene_alleles)")
    return create_engine(url)


def _load_allele_lookup(engine: Engine) -> Tuple[Dict[str, List[str]], Dict[Tuple[str, str], Tuple[int, str, str]]]:
    """
    Returns:
      token_to_basecodes: token(lower) -> [basecode_lower, ...]
      base_token_to_info: (basecode_lower, token_lower) -> (allele_number, allele_name, allele_nickname)

    Token matches against allele_name OR allele_nickname OR nickname.
    """
    sql = text(
        """
        SELECT
          lower(transgene_base_code) AS base_code,
          allele_number,
          lower(btrim(allele_name)) AS allele_name_lc,
          lower(btrim(allele_nickname)) AS allele_nickname_lc,
          lower(btrim(nickname)) AS nickname_lc,
          btrim(allele_name) AS allele_name,
          btrim(allele_nickname) AS allele_nickname
        FROM public.transgene_alleles
        WHERE coalesce(btrim(transgene_base_code),'') <> ''
          AND allele_number IS NOT NULL
          AND coalesce(btrim(allele_name),'') <> ''
          AND coalesce(btrim(allele_nickname),'') <> '';
        """
    )
    with engine.begin() as cx:
        rows = cx.execute(sql).fetchall()

    token_to_basecodes: Dict[str, List[str]] = {}
    base_token_to_info: Dict[Tuple[str, str], Tuple[int, str, str]] = {}

    for base_code, allele_number, an_lc, ann_lc, nick_lc, an, ann in rows:
        base = str(base_code)
        anum = int(allele_number)
        an_s = str(an)
        ann_s = str(ann)

        for tok in [an_lc, ann_lc, nick_lc]:
            if tok is None:
                continue
            t = str(tok).strip()
            if not t:
                continue
            token_to_basecodes.setdefault(t, [])
            if base not in token_to_basecodes[t]:
                token_to_basecodes[t].append(base)
            base_token_to_info[(base, t)] = (anum, an_s, ann_s)

    for t in token_to_basecodes:
        token_to_basecodes[t] = sorted(token_to_basecodes[t])

    return token_to_basecodes, base_token_to_info


def main() -> None:
    ap = argparse.ArgumentParser(description="v9: prepare legacy_clutches_v9.csv for loader_legacy_clutches.py (strict)")
    ap.add_argument("--in-csv", required=True, help="Input legacy_clutches_v9.csv (MUST include legacy_clutch_key)")
    ap.add_argument("--out-csv", required=True, help="Output legacy_clutches_v9_for_loader.csv")
    ap.add_argument(
        "--roi-compat-csv",
        default="seed_kits/legacy_wrangling_v4/working/legacy_imaging_annotations_for_db_v9_compat.csv",
        help="ROI compat CSV (must include legacy_clutch_key + roi_dir)",
    )
    ap.add_argument(
        "--roi-for-db-csv",
        default="seed_kits/legacy_wrangling_v4/working/legacy_imaging_annotations_for_db_v9.csv",
        help="ROI for_db CSV (must include roi_dir + genotype_base_codes + genotype_allele_codes)",
    )
    args = ap.parse_args()

    in_p = Path(args.in_csv)
    out_p = Path(args.out_csv)
    roi_compat_p = Path(args.roi_compat_csv)
    roi_for_db_p = Path(args.roi_for_db_csv)

    df_cl = _load_csv(in_p)
    df_compat = _load_csv(roi_compat_p)
    df_db = _load_csv(roi_for_db_p)

    for col in ["clutch_code", "legacy_clutch_key", "date_born", "roi_count", "parent_female_genotype_text", "parent_male_genotype_text"]:
        if col not in df_cl.columns:
            raise SystemExit(f"[STOP] in-csv missing required column: {col}")

    for col in ["legacy_clutch_key", "roi_dir"]:
        if col not in df_compat.columns:
            raise SystemExit(f"[STOP] roi-compat-csv missing required column: {col} (path={roi_compat_p})")

    for col in ["roi_dir", "genotype_base_codes", "genotype_allele_codes"]:
        if col not in df_db.columns:
            raise SystemExit(f"[STOP] roi-for-db-csv missing required column: {col} (path={roi_for_db_p})")

    df_compat = df_compat[["legacy_clutch_key", "roi_dir"]].copy()
    df_compat["legacy_clutch_key"] = df_compat["legacy_clutch_key"].astype(str).str.strip()
    df_compat["roi_dir"] = df_compat["roi_dir"].astype(str).str.strip()

    df_db = df_db[["roi_dir", "genotype_base_codes", "genotype_allele_codes"]].copy()
    df_db["roi_dir"] = df_db["roi_dir"].astype(str).str.strip()

    j = df_compat.merge(df_db, on="roi_dir", how="inner")
    if j.empty:
        raise SystemExit("[STOP] join roi_compat ↔ roi_for_db on roi_dir produced 0 rows")

    # Build clutch-level allele pairs from ROI rows (positional pairing).
    # Key rule: allele_nickname is only meaningful WITHIN a basecode; do not infer token→base globally.

    def _split_pipe_keep_order(raw: object) -> List[str]:
        if not _nonempty(raw):
            return []
        parts = [p.strip() for p in TOKEN_SPLIT.split(str(raw)) if p.strip()]
        out: List[str] = []
        for p in parts:
            c = _canon_basecode(p)
            if c:
                out.append(c)
        return out

    def _split_alleles_keep_order(raw: object) -> List[str]:
        if not _nonempty(raw):
            return []
        parts = [p.strip() for p in TOKEN_SPLIT.split(str(raw)) if p.strip()]
        out: List[str] = []
        for p in parts:
            x = str(p).strip()
            if not x:
                continue
            xl = x.lower()
            if xl in ("nan", "none", "na", "n/a", "<na>"):
                continue
            if x.endswith(".0") and x[:-2].isdigit():
                x = x[:-2]
            out.append(x)
        return out

    j["base_list"] = j["genotype_base_codes"].apply(_split_pipe_keep_order)
    j["allele_list"] = j["genotype_allele_codes"].apply(_split_alleles_keep_order)

    eng = _get_engine()
    token_to_bases, base_token_to_info = _load_allele_lookup(eng)

    qc_rows: List[Dict[str, str]] = []
    display_by_key: Dict[str, str] = {}

    # Collect pairs per clutch
    pairs_by_key: Dict[str, Dict[str, List[str]]] = {}

    for r in j.itertuples(index=False):
        lk = str(r.legacy_clutch_key).strip()
        bases = list(getattr(r, "base_list"))
        toks  = list(getattr(r, "allele_list"))

        if not lk or not bases or not toks:
            continue

        if len(bases) == 1 and len(toks) >= 1:
            # replicate the single base for all tokens
            bases = [bases[0]] * len(toks)
        elif len(bases) != len(toks):
            qc_rows.append(
                {
                    "legacy_clutch_key": lk,
                    "genotype_base_codes": "|".join(bases),
                    "genotype_allele_codes": "|".join(toks),
                    "error": f"basecode/token count mismatch in ROI row: n_basecodes={len(bases)} n_allele_tokens={len(toks)}",
                }
            )
            continue

        per_base = pairs_by_key.setdefault(lk, {})
        for b_raw, tok_raw in zip(bases, toks):
            b = _canon_basecode(b_raw)
            t = str(tok_raw).strip().lower()
            if not b or not t:
                continue
            if (b, t) not in base_token_to_info:
                qc_rows.append(
                    {
                        "legacy_clutch_key": lk,
                        "genotype_base_codes": "|".join(bases),
                        "genotype_allele_codes": "|".join(toks),
                        "error": f"allele token '{tok_raw}' not found for basecode='{b}' in transgene_alleles (allele_name/allele_nickname/nickname)",
                    }
                )
                per_base.clear()
                break
            per_base.setdefault(b, [])
            if t not in per_base[b]:
                per_base[b].append(t)

    # Build display strings per clutch from resolved (base, token) pairs
    for lk, per_base in pairs_by_key.items():
        if not per_base:
            display_by_key[lk] = ""
            continue

        out_parts: List[str] = []
        for b in sorted(per_base.keys()):
            infos: List[Tuple[int, str, str]] = []
            for t in per_base[b]:
                info = base_token_to_info.get((b, t))
                if not info:
                    infos = []
                    break
                infos.append(info)
            if not infos:
                out_parts = []
                break
            infos = sorted(infos, key=lambda x: x[0])
            inner = "; ".join([f"tg({b}){an}-{ann}" for (_anum, an, ann) in infos])
            out_parts.append(inner)

        display_by_key[lk] = "; ".join(out_parts) if out_parts else ""

    if qc_rows:
        qc_p = out_p.parent / "qc_unpairable_genotype_alleles_in_clutch_loader_input.csv"
        pd.DataFrame(qc_rows).to_csv(qc_p, index=False)
        sample = pd.DataFrame(qc_rows).head(30).to_string(index=False)
        raise SystemExit(
            f"[STOP] {len(qc_rows)} legacy_clutch_key(s) have unpairable allele tokens (DB pairing failed).\n"
            f"QC written: {qc_p}\nSample:\n{sample}"
        )

    # Build clutch-level aggregates from resolved pairs
    agg_rows = []
    for lk, per_base in pairs_by_key.items():
        if not per_base:
            continue
        basecodes = sorted(per_base.keys())
        allele_toks = sorted({t for toks in per_base.values() for t in toks})
        agg_rows.append({
            "legacy_clutch_key": lk,
            "genotype_basecodes": "|".join(basecodes),
            "genotype_allele_nicknames": "|".join(allele_toks),
        })
    agg = pd.DataFrame(agg_rows, columns=["legacy_clutch_key","genotype_basecodes","genotype_allele_nicknames"])

    out = pd.DataFrame()
    out["clutch_code"] = df_cl["clutch_code"].astype(str).str.strip()
    out["legacy_clutch_key"] = df_cl["legacy_clutch_key"].astype(str).str.strip()
    out["parent_female_genotype_text"] = df_cl["parent_female_genotype_text"].astype(str).str.strip()
    out["parent_male_genotype_text"] = df_cl["parent_male_genotype_text"].astype(str).str.strip()
    out["date_born"] = df_cl["date_born"].astype(str).str.strip()
    out["roi_count"] = df_cl["roi_count"]

    if "datasets" in df_cl.columns:
        out["datasets"] = df_cl["datasets"].astype(str).str.strip()
    else:
        out["datasets"] = pd.NA

    out = out[out["clutch_code"].apply(_nonempty)].copy()

    out = out.merge(agg, on="legacy_clutch_key", how="left")
    out["genotype_basecodes"] = out["genotype_basecodes"].fillna("").astype(str)
    out["genotype_allele_nicknames"] = out["genotype_allele_nicknames"].fillna("").astype(str)
    out["genotype_alleles_display"] = out["legacy_clutch_key"].map(lambda k: display_by_key.get(str(k).strip(), "")).fillna("").astype(str)

    out_p.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_p, index=False)

    print("v9_prepare_legacy_clutches_for_loader:")
    print(f"  input:        {in_p}")
    print(f"  roi_compat:   {roi_compat_p}")
    print(f"  roi_for_db:   {roi_for_db_p}")
    print(f"  output:       {out_p} (n={len(out)})")
    print("  genotype_key: legacy_clutch_key → genotype_basecodes + genotype_allele_nicknames + genotype_alleles_display")


if __name__ == "__main__":
    main()
