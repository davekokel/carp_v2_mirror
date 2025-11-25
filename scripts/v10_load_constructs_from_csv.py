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
        description="v10: load constructs from constructs_plasmid.csv into plasmids + transgenes"
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

    path = Path(args.constructs_csv)
    if not path.exists():
        raise SystemExit(f"constructs_plasmid.csv not found: {path}")

    df = pd.read_csv(path)
    print(f"[v10_load_constructs] read {len(df)} row(s) from {path}")

    # Expect at least these columns; adapt as needed.
    required = ["plasmid_code", "plasmid_name"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"constructs CSV missing required columns: {missing}; found {list(df.columns)}")

    df = df.copy()
    df["plasmid_code"] = df["plasmid_code"].astype(str).str.strip()
    df["plasmid_name"] = df["plasmid_name"].astype(str).str.strip()
    df["plasmid_nickname"] = df.get("plasmid_nickname", "").astype(str).fillna("").str.strip()
    df["resistance"] = df.get("resistance", "").astype(str).fillna("").str.strip()
    df["notes"] = df.get("plasmid_notes", df.get("notes", "")).astype(str).fillna("").str.strip()

    df = df[df["plasmid_code"] != ""].drop_duplicates(subset=["plasmid_code"])

    engine = get_engine(args.db_url)

    sql_upsert_plasmid = text(
        """
        INSERT INTO public.plasmids (
          code,
          plasmid_base_code,
          name,
          nickname,
          notes,
          resistance,
          created_at
        )
        VALUES (
          :code,
          :code,
          :name,
          :nickname,
          :notes,
          :resistance,
          now()
        )
        ON CONFLICT (code) DO UPDATE SET
          name       = EXCLUDED.name,
          nickname   = EXCLUDED.nickname,
          notes      = EXCLUDED.notes,
          resistance = EXCLUDED.resistance
        """
    )

    sql_upsert_transgene = text(
        """
        INSERT INTO public.transgenes (
          transgene_base_code,
          transgene_name,
          description,
          created_at
        )
        VALUES (
          :code,
          :name,
          :notes,
          now()
        )
        ON CONFLICT (transgene_base_code) DO UPDATE SET
          transgene_name = EXCLUDED.transgene_name,
          description    = EXCLUDED.description
        """
    )

    inserted_plasmids = 0
    inserted_transgenes = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            code = row["plasmid_code"]
            name = row["plasmid_name"]
            nickname = row["plasmid_nickname"]
            resistance = row["resistance"]
            notes = row["notes"]

            cx.execute(
                sql_upsert_plasmid,
                {
                    "code": code,
                    "name": name,
                    "nickname": nickname,
                    "notes": notes,
                    "resistance": resistance,
                },
            )
            inserted_plasmids += 1

            cx.execute(
                sql_upsert_transgene,
                {
                    "code": code,
                    "name": name,
                    "notes": notes,
                },
            )
            inserted_transgenes += 1

    print(f"[v10_load_constructs] upserted {inserted_plasmids} plasmid row(s)")
    print(f"[v10_load_constructs] upserted {inserted_transgenes} transgene row(s)")


if __name__ == "__main__":
    main()
