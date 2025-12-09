#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from carp_app.etl.constructs_v10_shared import load_constructs_from_df


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: load constructs from constructs_plasmid.csv "
        "(canonical codes, plasmid kind, injection use flags)."
    )
    parser.add_argument(
        "--constructs-csv",
        required=True,
        help="Path to constructs_plasmid.csv",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    csv_path = Path(args.constructs_csv)
    if not csv_path.exists():
        raise SystemExit(f"[v10_load_constructs] CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    print(f"[v10_load_constructs] read {len(df)} row(s) from {csv_path}")

    engine = get_engine(args.db_url)

    with engine.begin() as cx:
        summary = load_constructs_from_df(df, cx)

    print(
        f"[v10_load_constructs] unique plasmid_code rows: {summary['n_base_rows']} "
        f"(from {summary['n_csv_rows']} CSV rows)"
    )
    print(f"[v10_load_constructs] upserted {summary['n_upserted']} construct(s)")
    if summary["n_rejected"]:
        print(
            f"[v10_load_constructs] WARNING: {summary['n_rejected']} row(s) "
            "were rejected (see rejected_rows in shared loader)."
        )


if __name__ == "__main__":
    main()
