#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")


def main() -> None:
    ap = argparse.ArgumentParser(description="v9: prepare legacy_clutches_v9.csv for loader_legacy_clutches.py (strict)")
    ap.add_argument("--in-csv", required=True, help="Input legacy_clutches_v9.csv (MUST include legacy_clutch_key)")
    ap.add_argument("--out-csv", required=True, help="Output legacy_clutches_v9_for_loader.csv")
    args = ap.parse_args()

    in_p = Path(args.in_csv)
    out_p = Path(args.out_csv)

    if not in_p.exists():
        raise SystemExit(f"input CSV not found: {in_p}")

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
        raise SystemExit(f"v9_prepare_legacy_clutches_for_loader: missing required columns: {missing}")

    out = pd.DataFrame()
    out["clutch_code"] = df["clutch_code"].astype(str).str.strip()
    out["legacy_clutch_key"] = df["legacy_clutch_key"].astype(str).str.strip()
    out["parent_female"] = df["parent_female_genotype_text"].astype(str).str.strip()
    out["parent_male"] = df["parent_male_genotype_text"].astype(str).str.strip()
    out["date_born"] = df["date_born"].astype(str).str.strip()
    out["roi_count"] = df["roi_count"]

    if "legacy_clutch_group" in df.columns:
        out["legacy_clutch_group"] = df["legacy_clutch_group"]
    else:
        out["legacy_clutch_group"] = pd.NA

    out = out[out["clutch_code"].apply(_nonempty)].copy()

    bad = out[~out["legacy_clutch_key"].apply(_nonempty)]
    if len(bad):
        raise SystemExit(f"[STOP] {len(bad)} row(s) missing legacy_clutch_key after prep (this must be nonblank)")

    out_p.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_p, index=False)

    print("v9_prepare_legacy_clutches_for_loader:")
    print(f"  input:  {in_p}")
    print(f"  output: {out_p} (n={len(out)})")


if __name__ == "__main__":
    main()
