from __future__ import annotations

import sys
import pathlib
from pathlib import Path
from typing import List

import pandas as pd
from sqlalchemy import text

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.lib.app_ctx import get_engine  # type: ignore[import]


LEGACY_CLUTCHES_CSV = Path("seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9.csv")
LEGACY_ROI_CSV = Path("seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv")


def main() -> None:
    eng = get_engine()

    with eng.begin() as cx:
        star = pd.read_sql(
            text(
                """
                SELECT
                  clutch_code,
                  clutch_date,
                  genotype_base_codes,
                  treat_codes
                FROM public.v11_clutch_star
                WHERE COALESCE(genotype_base_codes,'') = ''
                  OR COALESCE(treat_codes,'') = ''
                ORDER BY clutch_code
                """
            ),
            cx,
        )

    def nz(s) -> str:
        return "" if pd.isna(s) else str(s)

    unresolved_codes: List[str] = sorted({nz(c) for c in star["clutch_code"].tolist() if nz(c)})

    print("=== v11_clutch_star (current semantics; missing genotype and/or treatment) ===")
    print(star.to_string(index=False))

    if not unresolved_codes:
        print("\n[INFO] No unresolved clutches.")
        return

    if not LEGACY_CLUTCHES_CSV.exists():
        print(f"\n[WARN] {LEGACY_CLUTCHES_CSV} not found; cannot show parent/treatment basecodes.")
        return

    if not LEGACY_ROI_CSV.exists():
        print(f"\n[WARN] {LEGACY_ROI_CSV} not found; cannot show legacy ROI treatment columns.")
        return

    df_cl = pd.read_csv(LEGACY_CLUTCHES_CSV)
    df_roi = pd.read_csv(LEGACY_ROI_CSV)

    df_cl["clutch_code"] = df_cl["clutch_code"].astype(str).str.strip()

    cl = df_cl[df_cl["clutch_code"].isin(unresolved_codes)].copy()

    print("\n=== legacy_clutches_v9.csv (parents + treatment basecodes) ===")
    cl_cols = [
        "clutch_code",
        "legacy_clutch_key",
        "parent_female_genotype_text",
        "parent_male_genotype_text",
        "treatment_rna_rna_base_code",
        "treatment_plasmid_plasmid_base_code",
    ]
    cl_cols = [c for c in cl_cols if c in cl.columns]
    if cl_cols:
        print(cl[cl_cols].to_string(index=False))
    else:
        print("(no matching columns in legacy_clutches_v9.csv)")

    df_roi["legacy_clutch_key"] = df_roi["legacy_clutch_key"].astype(str).str.strip()
    keys = cl["legacy_clutch_key"].dropna().astype(str).str.strip().unique().tolist()

    roi = df_roi[df_roi["legacy_clutch_key"].isin(keys)].copy()

    print("\n=== legacy_imaging_annotations_for_db_v9.csv (ROI paths + treatment cols) ===")
    roi_cols = [
        "legacy_clutch_key",
        "dataset",
        "roi_name",
        "treatment_rna_rna_base_code",
        "treatment_plasmid_plasmid_base_code",
        "treatment_rna_rna_base_code_from_enrich",
        "treatment_plasmid_plasmid_base_code_from_enrich",
    ]
    roi_cols = [c for c in roi_cols if c in roi.columns]
    if roi_cols:
        print(roi[roi_cols].to_string(index=False))
    else:
        print("(no matching treatment columns in ROI CSV)")

    with eng.begin() as cx:
        rois = pd.read_sql(
            text(
                """
                SELECT
                  clutch_code,
                  plate_code,
                  experiment_date,
                  slot_label,
                  slot_index,
                  roi_code,
                  roi_index,
                  roi_note_anatomy,
                  roi_path
                FROM public.v11_imaging_roi_star
                WHERE clutch_code = ANY(:codes)
                ORDER BY clutch_code, plate_code, slot_label, roi_index
                """
            ),
            cx,
            params={"codes": unresolved_codes},
        )

    print("\n=== v11_imaging_roi_star (ROI mapping into schema) ===")
    if rois.empty:
        print("(no v11_imaging_roi_star rows for these clutches)")
    else:
        print(rois.to_string(index=False))


if __name__ == "__main__":
    main()
