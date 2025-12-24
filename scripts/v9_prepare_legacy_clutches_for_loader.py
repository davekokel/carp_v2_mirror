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

    j["base_tokens"] = j["genotype_base_codes"].apply(_split_tokens_pipe)
    j["allele_tokens"] = j["genotype_allele_codes"].apply(_split_allele_tokens)

    agg = (
        j.groupby("legacy_clutch_key", dropna=False)
        .agg(
            genotype_basecodes=("base_tokens", lambda s: "|".join(sorted(set(sum(s.tolist(), [])))) if len(s) else ""),
            genotype_allele_nicknames=("allele_tokens", lambda s: "|".join(sorted(set(sum(s.tolist(), [])))) if len(s) else ""),
        )
        .reset_index()
    )

    eng = _get_engine()
    token_to_bases, base_token_to_info = _load_allele_lookup(eng)

    qc_rows: List[Dict[str, str]] = []
    display_by_key: Dict[str, str] = {}

    for r in agg.itertuples(index=False):
        lk = str(r.legacy_clutch_key).strip()
        basecodes = _split_tokens_pipe(r.genotype_basecodes)
        allele_toks = _split_allele_tokens(r.genotype_allele_nicknames)

        if not lk or not basecodes or not allele_toks:
            display_by_key[lk] = ""
            continue

        tok_to_base: Dict[str, str] = {}
        for tok in allele_toks:
            t = tok.strip().lower()
            if not t:
                continue
            bases = token_to_bases.get(t, [])
            if not bases:
                qc_rows.append(
                    {
                        "legacy_clutch_key": lk,
                        "genotype_base_codes": "|".join(basecodes),
                        "genotype_allele_codes": "|".join(allele_toks),
                        "error": f"allele token '{tok}' not found in transgene_alleles (allele_name/allele_nickname/nickname)",
                    }
                )
                tok_to_base = {}
                break
            if len(bases) != 1:
                qc_rows.append(
                    {
                        "legacy_clutch_key": lk,
                        "genotype_base_codes": "|".join(basecodes),
                        "genotype_allele_codes": "|".join(allele_toks),
                        "error": f"allele token '{tok}' is ambiguous across basecodes={bases}",
                    }
                )
                tok_to_base = {}
                break
            tok_to_base[t] = bases[0]

        if not tok_to_base:
            continue

        extra_bases = sorted(set(tok_to_base.values()) - set(basecodes))
        if extra_bases:
            qc_rows.append(
                {
                    "legacy_clutch_key": lk,
                    "genotype_base_codes": "|".join(basecodes),
                    "genotype_allele_codes": "|".join(allele_toks),
                    "error": f"allele token(s) map to basecode(s) not present in genotype_base_codes: {extra_bases}",
                }
            )
            continue

        per_base: Dict[str, List[str]] = {}
        for tok in allele_toks:
            t = tok.strip().lower()
            b = tok_to_base.get(t)
            if not b:
                continue
            per_base.setdefault(b, []).append(t)

        missing_for_base = [b for b in basecodes if b not in per_base]
        if missing_for_base:
            qc_rows.append(
                {
                    "legacy_clutch_key": lk,
                    "genotype_base_codes": "|".join(basecodes),
                    "genotype_allele_codes": "|".join(allele_toks),
                    "error": f"no allele token mapped to basecode(s)={missing_for_base}",
                }
            )
            continue

        out_parts: List[str] = []
        for b in basecodes:
            toks_for_b = sorted(dict.fromkeys(per_base.get(b, [])))
            infos: List[Tuple[int, str, str]] = []
            for t in toks_for_b:
                info = base_token_to_info.get((b, t))
                if not info:
                    qc_rows.append(
                        {
                            "legacy_clutch_key": lk,
                            "genotype_base_codes": "|".join(basecodes),
                            "genotype_allele_codes": "|".join(allele_toks),
                            "error": f"internal: missing allele_name/nickname for basecode='{b}' token='{t}'",
                        }
                    )
                    infos = []
                    break
                infos.append(info)

            if not infos:
                out_parts = []
                break

            infos = sorted(infos, key=lambda x: x[0])
            inner = "; ".join([f"tg({b}){an}-{ann}" for (_anum, an, ann) in infos])
            out_parts.append(inner)

        if out_parts:
            display_by_key[lk] = "; ".join(out_parts)

    if qc_rows:
        qc_p = out_p.parent / "qc_unpairable_genotype_alleles_in_clutch_loader_input.csv"
        pd.DataFrame(qc_rows).to_csv(qc_p, index=False)
        sample = pd.DataFrame(qc_rows).head(30).to_string(index=False)
        raise SystemExit(
            f"[STOP] {len(qc_rows)} legacy_clutch_key(s) have unpairable allele tokens (DB pairing failed).\n"
            f"QC written: {qc_p}\nSample:\n{sample}"
        )

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
