#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

_TOKEN_SPLIT = re.compile(r"[|,; ]+")
_TOKEN_RE = re.compile(r"^([A-Za-z]+)[-_]?(0*)(\d+)$")


def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")


def canon_one(tok: str) -> str | None:
    s = (tok or "").strip()
    if not s:
        return None
    m = _TOKEN_RE.match(s)
    if not m:
        return s.lower()
    prefix = m.group(1).lower()
    num = int(m.group(3))
    if prefix == "swin":
        prefix = "pswin"
    return f"{prefix}-{num}"


def canon_tokens(raw_codes: str) -> list[str]:
    parts = [p.strip() for p in _TOKEN_SPLIT.split(raw_codes or "") if p.strip()]
    out: list[str] = []
    for p in parts:
        c = canon_one(p)
        if c:
            out.append(c)
    out = sorted(dict.fromkeys(out))
    return out


def _agg_basecodes(series: pd.Series) -> str | None:
    toks: list[str] = []
    for v in series.tolist():
        if not _nonempty(v):
            continue
        toks.extend(canon_tokens(str(v)))
    toks = sorted(dict.fromkeys(toks))
    return "|".join(toks) if toks else None


def main() -> None:
    ap = argparse.ArgumentParser(
        description="v9: prepare legacy_clutches_v9.csv for loader_legacy_clutches.py (STRICT, no renames; adds genotype_basecodes)"
    )
    ap.add_argument("--in-csv", required=True, help="Input legacy_clutches_v9.csv (MUST include legacy_clutch_key)")
    ap.add_argument("--out-csv", required=True, help="Output legacy_clutches_v9_for_loader.csv")

    ap.add_argument(
        "--roi-compat-csv",
        default="seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9_compat.csv",
        help="ROI compat CSV (must include roi_dir + legacy_clutch_key)",
    )
    ap.add_argument(
        "--roi-for-db-csv",
        default="seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9.csv",
        help="ROI for_db CSV (must include roi_dir + genotype_base_codes)",
    )
    args = ap.parse_args()

    in_p = Path(args.in_csv)
    out_p = Path(args.out_csv)
    roi_compat_p = Path(args.roi_compat_csv)
    roi_for_db_p = Path(args.roi_for_db_csv)

    for p in [in_p, roi_compat_p, roi_for_db_p]:
        if not p.exists():
            raise SystemExit(f"[STOP] file not found: {p}")

    df = pd.read_csv(in_p, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    required = [
        "clutch_code",
        "legacy_clutch_key",
        "date_born",
        "roi_count",
        "parent_female_genotype_text",
        "parent_male_genotype_text",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"[STOP] v9_prepare_legacy_clutches_for_loader: missing required columns: {missing}")

    df_c = pd.read_csv(roi_compat_p, low_memory=False)
    df_c.columns = [str(c).strip() for c in df_c.columns]
    need_c = ["roi_dir", "legacy_clutch_key"]
    miss_c = [c for c in need_c if c not in df_c.columns]
    if miss_c:
        raise SystemExit(f"[STOP] roi-compat-csv missing required columns: {miss_c}")

    df_db = pd.read_csv(roi_for_db_p, low_memory=False)
    df_db.columns = [str(c).strip() for c in df_db.columns]
    need_db = ["roi_dir", "genotype_base_codes"]
    miss_db = [c for c in need_db if c not in df_db.columns]
    if miss_db:
        raise SystemExit(f"[STOP] roi-for-db-csv missing required columns: {miss_db}")

    df_db = df_db[["roi_dir", "genotype_base_codes"]].copy()
    df_db["roi_dir"] = df_db["roi_dir"].astype(str).str.strip()
    df_db["genotype_base_codes"] = df_db["genotype_base_codes"].astype("string")

    df_c = df_c[["roi_dir", "legacy_clutch_key"]].copy()
    df_c["roi_dir"] = df_c["roi_dir"].astype(str).str.strip()
    df_c["legacy_clutch_key"] = df_c["legacy_clutch_key"].astype(str).str.strip()

    df_roi = df_c.merge(df_db, on="roi_dir", how="left")

    df_key = (
        df_roi.groupby("legacy_clutch_key", dropna=False)
        .agg({"genotype_base_codes": _agg_basecodes})
        .reset_index()
        .rename(columns={"genotype_base_codes": "genotype_basecodes"})
    )

    out = pd.DataFrame()
    out["clutch_code"] = df["clutch_code"].astype(str).str.strip()
    out["legacy_clutch_key"] = df["legacy_clutch_key"].astype(str).str.strip()
    out["date_born"] = df["date_born"].astype(str).str.strip()
    out["roi_count"] = df["roi_count"]
    out["parent_female_genotype_text"] = df["parent_female_genotype_text"].astype("string")
    out["parent_male_genotype_text"] = df["parent_male_genotype_text"].astype("string")

    if "datasets" in df.columns:
        out["datasets"] = df["datasets"].astype("string")
    else:
        out["datasets"] = pd.NA

    if "legacy_clutch_group" in df.columns:
        out["legacy_clutch_group"] = df["legacy_clutch_group"]
    else:
        out["legacy_clutch_group"] = pd.NA

    out = out.merge(df_key, on="legacy_clutch_key", how="left")

    out = out[out["clutch_code"].apply(_nonempty)].copy()

    bad_key = out[~out["legacy_clutch_key"].apply(_nonempty)]
    if len(bad_key):
        raise SystemExit(f"[STOP] {len(bad_key)} row(s) missing legacy_clutch_key after prep (must be nonblank)")

    bad_geno = out[~out["genotype_basecodes"].apply(_nonempty)].copy()
    if len(bad_geno):
        sample = bad_geno[["clutch_code", "legacy_clutch_key"]].head(40)
        qc_path = out_p.parent / "qc_missing_genotype_basecodes_in_clutch_loader_input.csv"
        bad_geno.to_csv(qc_path, index=False)
        raise SystemExit(
            "[STOP] "
            + f"{len(bad_geno)} clutch row(s) missing genotype_basecodes after ROI join.\n"
            + f"QC written: {qc_path}\n"
            + "Sample:\n"
            + sample.to_string(index=False)
        )

    out_p.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_p, index=False)

    print("v9_prepare_legacy_clutches_for_loader:")
    print(f"  input:        {in_p}")
    print(f"  roi_compat:   {roi_compat_p}")
    print(f"  roi_for_db:   {roi_for_db_p}")
    print(f"  output:       {out_p} (n={len(out)})")
    print(f"  genotype_key: legacy_clutch_key → genotype_basecodes (canonicalized)")


if __name__ == "__main__":
    main()
