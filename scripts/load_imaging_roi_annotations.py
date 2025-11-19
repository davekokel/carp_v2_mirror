from __future__ import annotations

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import psycopg2


def get_db_url() -> str:
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set.")
    return db_url


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Annotations CSV not found: {path}")
    df = pd.read_csv(path)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load imaging ROI annotations into public.imaging_roi_annotations."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("seed_kits/legacy_wrangling/working/imaging_roi_annotations_AUTO.csv"),
        help="Path to imaging ROI annotations CSV",
    )
    parser.add_argument(
        "--source-system",
        default="legacy_imaging_auto",
        help="Value for source_system column",
    )
    parser.add_argument(
        "--import-batch-id",
        default=None,
        help="Optional import_batch_id for this load",
    )
    args = parser.parse_args()

    df = load_csv(args.csv)

    expected_cols = [
        "roi_dir",
        "parent_female",
        "parent_male",
        "genotype_pretty",
        "genotype_base_codes",
        "genotype_allele_codes",
        "genotype_marker_fluor_codes",
        "genotype_marker_tag_codes",
        "treatment_plasmid_base_codes",
        "treatment_rna_base_codes",
        "treatment_dye_base_codes",
        "treatment_marker_fluor_codes",
        "treatment_marker_tag_codes",
        "all_marker_fluor_codes",
    ]

    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    df = df[expected_cols].copy()

    df["source_system"] = args.source_system
    df["import_batch_id"] = args.import_batch_id

    cols_for_insert = expected_cols + ["source_system", "import_batch_id"]

    rows = []
    for _, row in df.iterrows():
        vals = []
        for col in cols_for_insert:
            v = row.get(col)
            if pd.isna(v):
                vals.append(None)
            else:
                vals.append(v)
        rows.append(tuple(vals))

    db_url = get_db_url()
    conn = psycopg2.connect(db_url)

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE public.imaging_roi_annotations;")
                placeholders = ", ".join(["%s"] * len(cols_for_insert))
                collist = ", ".join(cols_for_insert)
                sql = f"INSERT INTO public.imaging_roi_annotations ({collist}) VALUES ({placeholders})"
                cur.executemany(sql, rows)
        print(f"Loaded {len(rows)} imaging ROI annotation row(s) into public.imaging_roi_annotations.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
