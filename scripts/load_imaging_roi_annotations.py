from __future__ import annotations

import os
import argparse
from pathlib import Path

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
        help="(unused) legacy source_system argument",
    )
    parser.add_argument(
        "--import-batch-id",
        default=None,
        help="(unused) legacy import_batch_id argument",
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
        "treatment_marker_fluor_codes",
        "treatment_marker_tag_codes",
        "all_marker_fluor_codes",
        "plate_id_filled",
        "slot_id_filled",
        "roi_index_within_slot",
        "roi_code",
    ]

    # include fusion label columns if present in the CSV
    if "genotype_marker_fusion_labels" in df.columns:
        expected_cols.append("genotype_marker_fusion_labels")
    if "treatment_marker_fusion_labels" in df.columns:
        expected_cols.append("treatment_marker_fusion_labels")

    # include localization columns if present in the CSV
    if "genotype_marker_localizations" in df.columns:
        expected_cols.append("genotype_marker_localizations")
    if "treatment_marker_localizations" in df.columns:
        expected_cols.append("treatment_marker_localizations")

    # include fluor-localization label columns if present in the CSV
    if "genotype_marker_fluor_loc_labels" in df.columns:
        expected_cols.append("genotype_marker_fluor_loc_labels")
    if "treatment_marker_fluor_loc_labels" in df.columns:
        expected_cols.append("treatment_marker_fluor_loc_labels")
    if "all_marker_fluor_loc_labels" in df.columns:
        expected_cols.append("all_marker_fluor_loc_labels")

    # ensure all expected columns exist in the DataFrame
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    # deduplicate expected_cols to avoid duplicate column labels
    seen = set()
    dedup_cols = []
    for c in expected_cols:
        if c not in seen:
            dedup_cols.append(c)
            seen.add(c)
    expected_cols = dedup_cols

    df = df[expected_cols].copy()
    cols_for_insert = expected_cols

    rows = []
    for _, row in df.iterrows():
        vals = []
        for col in cols_for_insert:
            v = row.get(col)
            # at this point v should be a scalar; duplicate columns would have made it a Series
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