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
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v9: load genetic backgrounds from genetic_backgrounds_seed.csv into public.genetic_backgrounds."
    )
    parser.add_argument(
        "--csv",
        help="Path to genetic_backgrounds_seed.csv; default is under seed_kits/2025-11-15-121231-autoload/working",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    ROOT = Path(__file__).resolve().parents[1]
    base = ROOT / "seed_kits" / "2025-11-15-121231-autoload"
    default_csv = base / "working" / "genetic_backgrounds_seed.csv"
    csv_path = Path(args.csv) if args.csv else default_csv

    if not csv_path.exists():
        raise SystemExit(f"genetic_backgrounds_seed.csv not found: {csv_path}")

    df = pd.read_csv(csv_path)
    print(f"[v9_load_genetic_backgrounds_seed] read {len(df)} row(s) from {csv_path}")

    required = ["bg_code", "bg_name", "bg_category", "source_system", "description"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Seed CSV missing required columns {missing}; found {list(df.columns)}")

    df = df.copy()
    for col in required:
        df[col] = df[col].astype(str).fillna("")

    engine = get_engine(args.db_url)
    insert_sql = text(
        """
        INSERT INTO public.genetic_backgrounds (
          bg_code,
          bg_name,
          bg_category,
          source_system,
          description
        )
        VALUES (
          :bg_code,
          :bg_name,
          :bg_category,
          :source_system,
          :description
        )
        ON CONFLICT (bg_code) DO UPDATE SET
          bg_name       = EXCLUDED.bg_name,
          bg_category   = EXCLUDED.bg_category,
          source_system = EXCLUDED.source_system,
          description   = EXCLUDED.description
        """
    )

    inserted = 0
    with engine.begin() as cx:
        for _, row in df.iterrows():
            cx.execute(
                insert_sql,
                {
                    "bg_code": row["bg_code"].strip(),
                    "bg_name": row["bg_name"].strip(),
                    "bg_category": row["bg_category"].strip(),
                    "source_system": row["source_system"].strip(),
                    "description": row["description"].strip(),
                },
            )
            inserted += 1

    print(f"[v9_load_genetic_backgrounds_seed] upserted {inserted} row(s) into public.genetic_backgrounds")


if __name__ == "__main__":
    main()
