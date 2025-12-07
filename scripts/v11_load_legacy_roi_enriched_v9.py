#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List

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
        description="Load enriched legacy ROI annotations into raw.legacy_roi_enriched_v9"
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to legacy_imaging_annotations_for_db_v9.csv (enriched version)",
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

    # Map CSV columns -> DB columns.
    # These names are based on the snippet you pasted earlier.
    col_map = {
        # identity / keys
        "legacy_clutch_key": "legacy_clutch_key",
        "dataset": "dataset",
        "experiment_name": "experiment_name",
        "fish": "fish_label",
        "fish_number": "fish_number",
        "fish_age_hpf": "fish_age_hpf",
        "date_experiment": "date_experiment",
        "date_mount_yyyymmdd": "date_mount_yyyymmdd",
        "date_mount": "date_mount",
        "Date imaged": "date_imaged",
        "Date born_from_enrich": "date_born_from_enrich",

        # plate / slot / ROI placement
        "roi_name": "roi_name",
        "roi_index_within_slot": "roi_index_within_slot",
        "roi_tiffs": "roi_tiffs",
        "roi_dir": "roi_dir",
        "roi_folder": "roi_folder",
        "plate_date": "plate_date",
        "plate_key": "plate_key",
        "plate_id_filled": "plate_id_filled",
        "slot_id_filled": "slot_id_filled",
        "mount_id": "mount_id",
        "mount_id_inferred": "mount_id_inferred",
        "mount_id_source": "mount_id_source",
        "bruker_roi_id": "bruker_roi_id",

        # anatomy / locations
        "roi_anatomy_tokens": "roi_anatomy_tokens",
        "roi_anatomy": "roi_anatomy",
        "Imaged Locations": "imaged_locations",
        "all_unique_organelles": "all_unique_organelles",
        "all_fluor_organelles": "all_fluor_organelles",

        # parent genotypes (enriched)
        "ZF female genotype_from_enrich": "zf_female_genotype_from_enrich",
        "ZF male genotype_from_enrich": "zf_male_genotype_from_enrich",

        # child genotype basecodes / alleles (raw + slug)
        "genotype_base_codes_slug": "genotype_base_codes_slug",
        "genotype_allele_codes_slug": "genotype_allele_codes_slug",
        "genotype_base_codes": "genotype_base_codes",
        "genotype_allele_codes": "genotype_allele_codes",

        # child genotype marker rollups
        "genotype_marker_fluor_codes": "genotype_marker_fluor_codes",
        "genotype_marker_tag_codes": "genotype_marker_tag_codes",
        "genotype_marker_localizations": "genotype_marker_localizations",
        "genotype_marker_fusion_labels": "genotype_marker_fusion_labels",

        # treatment names / codes (sheet-level)
        "treatment_rna_names_sheet": "treatment_rna_names_sheet",
        "treatment_plasmid_names_sheet": "treatment_plasmid_names_sheet",
        "treatment_rna_codes_row": "treatment_rna_codes_row",
        "treatment_plasmid_codes_row": "treatment_plasmid_codes_row",

        # treatment basecodes (raw + enriched)
        "treatment_rna_base_codes_slug": "treatment_rna_base_codes_slug",
        "treatment_rna_rna_base_code": "treatment_rna_rna_base_code",
        "treatment_rna_rna_base_code_from_enrich": "treatment_rna_rna_base_code_from_enrich",
        "treatment_plasmid_plasmid_base_code": "treatment_plasmid_plasmid_base_code",
        "treatment_plasmid_plasmid_base_code_from_enrich": "treatment_plasmid_plasmid_base_code_from_enrich",

        # treatment marker rollups
        "treatment_marker_fluor_codes": "treatment_marker_fluor_codes",
        "treatment_marker_tag_codes": "treatment_marker_tag_codes",
        "treatment_marker_localizations": "treatment_marker_localizations",
        "treatment_marker_fluor_loc_labels": "treatment_marker_fluor_loc_labels",
    }

    missing: List[str] = [csv_col for csv_col in col_map.keys() if csv_col not in df.columns]
    if missing:
        print("[WARN] CSV missing expected columns (based on mapping):")
        for m in missing:
            print("  -", m)

    # Only keep columns that actually exist in the CSV
    usable_map = {csv_col: db_col for csv_col, db_col in col_map.items() if csv_col in df.columns}

    df_out = pd.DataFrame()
    for csv_col, db_col in usable_map.items():
        df_out[db_col] = df[csv_col]

    print(f"[INFO] legacy_roi_enriched_v9: importing {len(df_out)} row(s)")
    print("[INFO] Columns imported into raw.legacy_roi_enriched_v9:")
    for col in df_out.columns:
        print("  -", col)

    eng = get_engine(args.db_url)
    with eng.begin() as cx:
        cx.execute(text("TRUNCATE raw.legacy_roi_enriched_v9"))
        df_out.to_sql(
            "legacy_roi_enriched_v9",
            cx,
            schema="raw",
            if_exists="append",
            index=False,
        )

    print(f"[OK] loaded {len(df_out)} row(s) into raw.legacy_roi_enriched_v9")


if __name__ == "__main__":
    main()
