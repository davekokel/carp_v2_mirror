from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: ensure construct_fusions from constructs_plasmid.csv (constructs ↔ fusions)."
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
        raise SystemExit(f"constructs CSV not found: {path}")

    df = pd.read_csv(path)
    print(f"[v10_load_construct_fusions] read {len(df)} row(s) from {path}")

    required_cols = [
        "plasmid_code",
        "fluor_code",
        "tag_code",
        "tag_pos",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"[v10_load_construct_fusions] missing required columns in CSV: {missing}")

    # Normalize codes
    df["plasmid_code"] = df["plasmid_code"].astype(str).str.strip()
    df["fluor_code"] = df["fluor_code"].astype(str).str.strip()
    df["tag_code"] = df["tag_code"].astype(str).str.strip()
    df["tag_pos"] = df["tag_pos"].astype(str).str.strip()

    engine = get_engine(args.db_url)

    sql_find_construct = text(
        """
        SELECT c.id::text
        FROM public.constructs c
        LEFT JOIN public.construct_aliases a
          ON a.construct_id = c.id
        WHERE c.base_code = :code
           OR c.construct_code = :code
           OR a.alias = :code
        LIMIT 1
        """
    )

    sql_find_fluor = text(
        "SELECT id::text FROM public.fluors WHERE fluor_code = :code LIMIT 1"
    )

    sql_find_tag = text(
        "SELECT id::text FROM public.tags WHERE tag_code = :code LIMIT 1"
    )

    sql_upsert_fusion = text(
        """
        INSERT INTO public.fusions (fluor_id, tag_id, tag_pos, created_at)
        VALUES (:fluor_id, :tag_id, :tag_pos, now())
        RETURNING id::text AS fusion_id
        """
    )

    sql_find_fusion = text(
        """
        SELECT id::text AS fusion_id
        FROM public.fusions
        WHERE fluor_id = :fluor_id
          AND (
                (tag_id IS NULL AND :tag_id IS NULL)
             OR (tag_id = :tag_id)
          )
          AND COALESCE(tag_pos, '') = COALESCE(:tag_pos, '')
        LIMIT 1
        """
    )

    sql_insert_cf = text(
        """
        INSERT INTO public.construct_fusions (construct_id, fusion_id)
        VALUES (:construct_id, :fusion_id)
        ON CONFLICT (construct_id, fusion_id) DO NOTHING
        """
    )

    inserted_cf = 0
    skipped_no_construct = 0
    skipped_no_fluor = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            plasmid_code = row["plasmid_code"]
            fluor_code = row["fluor_code"]
            tag_code = row["tag_code"]
            tag_pos = row["tag_pos"]

            if not plasmid_code:
                continue

            # Find construct_id by base_code or construct_code = plasmid_code
            construct_id = cx.execute(sql_find_construct, {"code": plasmid_code}).scalar()
            if construct_id is None:
                print(f"[WARN] No construct for plasmid_code={plasmid_code}; skipping fusions for this row.")
                skipped_no_construct += 1
                continue

            # Skip rows with no fluor_code
            if not fluor_code or str(fluor_code).lower() in ("nan", "none", ""):
                skipped_no_fluor += 1
                continue

            fluor_id = cx.execute(sql_find_fluor, {"code": fluor_code}).scalar()
            if fluor_id is None:
                print(f"[WARN] No fluor_id for fluor_code={fluor_code}; skipping.")
                skipped_no_fluor += 1
                continue

            tag_id = None
            if tag_code and str(tag_code).lower() not in ("nan", "none", ""):
                tag_id = cx.execute(sql_find_tag, {"code": tag_code}).scalar()
                if tag_id is None:
                    print(f"[WARN] No tag_id for tag_code={tag_code}; using NULL tag.")
                    tag_id = None

            tag_pos_clean = tag_pos if tag_pos and str(tag_pos).lower() not in ("nan", "none", "") else None

            # Try to reuse an existing fusion first
            res = cx.execute(
                sql_find_fusion,
                {
                    "fluor_id": fluor_id,
                    "tag_id": tag_id,
                    "tag_pos": tag_pos_clean or "",
                },
            ).fetchone()

            if res is not None:
                fusion_id = res._mapping["fusion_id"]
            else:
                # Create new fusion
                res2 = cx.execute(
                    sql_upsert_fusion,
                    {
                        "fluor_id": fluor_id,
                        "tag_id": tag_id,
                        "tag_pos": tag_pos_clean,
                    },
                ).fetchone()
                fusion_id = res2._mapping["fusion_id"]

            # Link construct ↔ fusion
            cx.execute(
                sql_insert_cf,
                {
                    "construct_id": construct_id,
                    "fusion_id": fusion_id,
                },
            )
            inserted_cf += 1

    print(f"[v10_load_construct_fusions] linked {inserted_cf} construct_fusions row(s)")
    print(f"[v10_load_construct_fusions] skipped {skipped_no_construct} row(s) with no construct")
    print(f"[v10_load_construct_fusions] skipped {skipped_no_fluor} row(s) with no fluor")


if __name__ == "__main__":
    main()
