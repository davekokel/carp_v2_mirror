#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set (env DB_URL or --db-url)")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load legacy parent definitions (fish name -> plasmid_base_code, allele, injected_rna, injected_plasmid)"
    )
    parser.add_argument(
        "--csv",
        default="seed_kits/legacy_wrangling_v2/working/legacy_parent_definitions_v9.csv",
        help="Path to legacy_parent_definitions_v9.csv",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    expected_cols = ["parent_fish_name", "plasmid_base_code", "allele", "injected_rna", "injected_plasmid"]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"{csv_path} missing expected columns {missing}; columns={list(df.columns)}")

    # Normalize whitespace
    df_out = pd.DataFrame()
    for c in expected_cols:
        df_out[c] = df[c].astype(str).str.strip().where(~df[c].isna(), None)

    print("[INFO] legacy_parent_definitions_v9: sample rows:")
    print(df_out.head(15).to_string(index=False))

    eng = get_engine(args.db_url)
    with eng.begin() as cx:
        cx.execute(text("TRUNCATE raw.legacy_parent_definitions_v9"))
        df_out.to_sql(
            "legacy_parent_definitions_v9",
            cx,
            schema="raw",
            if_exists="append",
            index=False,
        )

    print(f"[OK] loaded {len(df_out)} row(s) into raw.legacy_parent_definitions_v9")


if __name__ == "__main__":
    main()
