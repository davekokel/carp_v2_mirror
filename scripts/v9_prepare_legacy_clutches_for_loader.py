from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare legacy_clutches_v9.csv into loader_legacy_clutches-compatible CSV."
    )
    parser.add_argument(
        "--in-csv",
        default="seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9.csv",
        help="Path to legacy_clutches_v9.csv",
    )
    parser.add_argument(
        "--out-csv",
        default="seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9_for_loader.csv",
        help="Output CSV path for loader_legacy_clutches.py",
    )
    args = parser.parse_args()

    in_path = Path(args.in_csv)
    out_path = Path(args.out_csv)

    if not in_path.exists():
        raise SystemExit(f"Input CSV not found: {in_path}")

    df = pd.read_csv(in_path)

    required = [
        "clutch_code",
        "date_born",
        "parent_female_genotype_text",
        "parent_male_genotype_text",
        "roi_count",
        "datasets",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"{in_path} is missing required columns: {missing}")

    out = pd.DataFrame(
        {
            "clutch_code": df["clutch_code"],
            # use genotype text as the best available "parent" label
            "parent_female": df["parent_female_genotype_text"].fillna(""),
            "parent_male": df["parent_male_genotype_text"].fillna(""),
            "date_born": df["date_born"].fillna(""),
            "roi_count": df["roi_count"].fillna(0).astype(int),
            # use datasets as a reasonable legacy_clutch_group summary
            "legacy_clutch_group": df["datasets"].fillna(""),
        }
    )

    out.to_csv(out_path, index=False)
    print("v9_prepare_legacy_clutches_for_loader:")
    print(f"  input:  {in_path}")
    print(f"  output: {out_path} (n={len(out)})")


if __name__ == "__main__":
    main()
