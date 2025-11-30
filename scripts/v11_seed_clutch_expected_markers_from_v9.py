from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


ROI_CSV = "seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv"
CLUTCHES_CSV = "seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9.csv"


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def first_nonempty(series: pd.Series) -> str:
    s = series.dropna().astype(str).str.strip()
    s = s[s != ""]
    return s.iloc[0] if len(s) else ""


def main() -> None:
    roi_path = Path(ROI_CSV)
    clutch_path = Path(CLUTCHES_CSV)

    if not roi_path.exists():
        raise SystemExit(f"ROI CSV not found: {roi_path}")
    if not clutch_path.exists():
        raise SystemExit(f"Clutches CSV not found: {clutch_path}")

    df_roi = pd.read_csv(roi_path)
    df_clutches = pd.read_csv(clutch_path)

    if "legacy_clutch_key" not in df_roi.columns:
        raise SystemExit("ROI CSV missing 'legacy_clutch_key'")
    if "legacy_clutch_key" not in df_clutches.columns or "clutch_code" not in df_clutches.columns:
        raise SystemExit("legacy_clutches_v9.csv must have 'legacy_clutch_key' and 'clutch_code'")

    # Map legacy_clutch_key -> clutch_code
    key_to_code: Dict[str, str] = {}
    for _, row in df_clutches.iterrows():
        key = str(row["legacy_clutch_key"])
        code = str(row["clutch_code"]).strip()
        if not code:
            continue
        key_to_code[key] = code

    # We care about genotype marker columns from the ROI CSV
    for col in ["genotype_marker_fusion_labels", "all_fluor_organelles"]:
        if col not in df_roi.columns:
            print(f"[WARN] ROI CSV missing column '{col}'; using empty values.")
            if col not in df_roi.columns:
                df_roi[col] = ""

    df_roi["legacy_clutch_key"] = df_roi["legacy_clutch_key"].fillna("").astype(str)

    # Group ROI rows by legacy_clutch_key and aggregate markers
    rows = []
    for key, grp in df_roi.groupby("legacy_clutch_key"):
        clutch_code = key_to_code.get(key)
        if not clutch_code:
            continue

        # dedupe fluor_tag labels
        fluor_tags = (
            grp["genotype_marker_fusion_labels"]
            .dropna()
            .astype(str)
            .str.strip()
        )
        fluor_tags = fluor_tags[fluor_tags != ""]
        if len(fluor_tags):
            fluor_tag_rollup = "; ".join(sorted(set(fluor_tags)))
        else:
            fluor_tag_rollup = ""

        org_labels = (
            grp["all_fluor_organelles"]
            .dropna()
            .astype(str)
            .str.strip()
        )
        org_labels = org_labels[org_labels != ""]
        if len(org_labels):
            org_rollup = "; ".join(sorted(set(org_labels)))
        else:
            org_rollup = ""

        if not fluor_tag_rollup and not org_rollup:
            # nothing to record for this clutch
            continue

        rows.append(
            {
                "legacy_clutch_key": key,
                "clutch_code": clutch_code,
                "all_fluor_tag_rollup": fluor_tag_rollup,
                "all_organelle_fluor_rollup": org_rollup,
            }
        )

    if not rows:
        print("[WARN] No clutch marker rows to write (no genotype markers found).")
        return

    df_markers = pd.DataFrame(rows)
    print(f"[INFO] Aggregated markers for {len(df_markers)} legacy clutches")

    eng = get_engine()

    # Map clutch_code -> clutch_id from DB
    with eng.begin() as cx:
        df_db_clutches = pd.read_sql(
            text(
                """
                SELECT id::text AS clutch_id, clutch_code
                FROM public.clutches
                WHERE source_system = 'legacy_imaging'
                """
            ),
            cx,
        )

    code_to_id: Dict[str, str] = dict(
        zip(df_db_clutches["clutch_code"].astype(str), df_db_clutches["clutch_id"].astype(str))
    )

    inserts = []
    for _, row in df_markers.iterrows():
        code = row["clutch_code"]
        clutch_id = code_to_id.get(code)
        if not clutch_id:
            continue
        inserts.append(
            {
                "clutch_id": clutch_id,
                "all_fluor_tag_rollup": row["all_fluor_tag_rollup"],
                "all_organelle_fluor_rollup": row["all_organelle_fluor_rollup"],
            }
        )

    if not inserts:
        print("[WARN] No DB clutch_ids matched for markers.")
        return

    with eng.begin() as cx:
        # wipe any existing rows for these clutches
        cx.execute(
            text(
                """
                DELETE FROM public.clutch_expected_genotypes_v11
                WHERE clutch_id::text = ANY(:ids)
                """
            ),
            {"ids": [i["clutch_id"] for i in inserts]},
        )
        # insert new rows
        for row in inserts:
            cx.execute(
                text(
                    """
                    INSERT INTO public.clutch_expected_genotypes_v11 (
                      clutch_id,
                      treatment_code,
                      genotype_basecode_code,
                      genotype_transgene_allele_code,
                      treatments_and_transgenes,
                      all_fluor_tag_rollup,
                      all_organelle_fluor_rollup,
                      zygocity_vector,
                      expected_fraction,
                      expected_percent_label,
                      is_enabled,
                      notes,
                      created_at,
                      created_by,
                      label
                    )
                    VALUES (
                      :clutch_id,
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      :all_fluor_tag_rollup,
                      :all_organelle_fluor_rollup,
                      NULL,
                      NULL,
                      NULL,
                      TRUE,
                      'seeded from legacy_imaging_annotations_for_db_v9.csv',
                      now(),
                      'v11_seed_clutch_expected_markers_from_v9.py',
                      NULL
                    )
                    """
                ),
                row,
            )

    print(f"[OK] Inserted {len(inserts)} clutch_expected_genotypes_v11 row(s).")


if __name__ == "__main__":
    main()
