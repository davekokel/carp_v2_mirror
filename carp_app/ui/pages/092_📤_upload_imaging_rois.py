from __future__ import annotations

import io
import re
import sys
import pathlib
from typing import List

import pandas as pd
import streamlit as st
from sqlalchemy import text

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock() -> None:
        ...

from carp_app.ui.lib.page_engine import engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Upload imaging ROIs",
    page_icon="📤",
    layout="wide",
)
st.title("📤 Upload imaging ROIs CSV")

st.markdown(
    """
Upload a CSV with columns exported from your aligned imaging sheet.
Each row should be one ROI for a fish on a Bruker plate/mount.
"""
)

uploaded_file = st.file_uploader("Choose imaging ROIs CSV", type=["csv"])

required_cols: List[str] = [
    "date_experiment",
    "fish_label",
    "roi_rel",
    "roi_name",
    "roi_tiffs",
    "roi_dir",
    "dataset",
    "experiment_name",
    "mount_row_index_scored",
    "date_mount",
    "mount_id",
    "zf_female_genotype",
    "zf_male_genotype",
    "additional_plasmids_injected",
    "additional_mrnas_injected",
    "additonal_proteins_injected",
    "additonal_dye_and_chemicals",
    "date_born",
    "time_mounted",
    "mounting_orientation",
    "date_screened_initial_feedback",
    "date_imaged",
    "data_location",
]


def parse_roi_index(roi_rel: str | None, roi_name: str | None) -> int:
    source = roi_rel or roi_name or ""
    m = re.search(r"(\d+)", str(source))
    if not m:
        return 1
    try:
        return int(m.group(1))
    except Exception:
        return 1


if uploaded_file is not None:
    data = uploaded_file.read()
    buffer = io.BytesIO(data)
    df = pd.read_csv(buffer)

    st.subheader("Preview of uploaded file")
    st.dataframe(df.head(20), use_container_width=True)

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {', '.join(missing)}")
        st.stop()

    st.subheader("Rows to import (all rows in this file)")
    with st.expander("Preview all (first 100 rows)", expanded=False):
        st.dataframe(df.head(100), use_container_width=True)

    if st.button("Import all ROIs in this file"):
        rows = df.copy()
        if rows.empty:
            st.warning("No rows found; nothing to import.")
            st.stop()

        inserted = 0

        with engine().begin() as cx:
            insert_raw_sql = text(
                """
                INSERT INTO raw.imaging_rois_raw (
                  date_experiment,
                  fish_label,
                  roi_rel,
                  roi_name,
                  roi_tiffs,
                  roi_dir,
                  dataset,
                  experiment_name,
                  mount_row_index_scored,
                  date_mount,
                  mount_id,
                  zf_female_genotype,
                  zf_male_genotype,
                  additional_plasmids_injected,
                  additional_mrnas_injected,
                  additonal_proteins_injected,
                  additonal_dye_and_chemicals,
                  date_born,
                  time_mounted,
                  mounting_orientation,
                  date_screened_initial_feedback,
                  date_imaged,
                  data_location,
                  female_plasmid_base_code,
                  female_allele,
                  male_plasmid_base_code,
                  male_allele,
                  additional_plasmids_plasmid_base_code,
                  additional_mrnas_plasmid_base_code
                )
                VALUES (
                  :date_experiment,
                  :fish_label,
                  :roi_rel,
                  :roi_name,
                  :roi_tiffs,
                  :roi_dir,
                  :dataset,
                  :experiment_name,
                  :mount_row_index_scored,
                  :date_mount,
                  :mount_id,
                  :zf_female_genotype,
                  :zf_male_genotype,
                  :additional_plasmids_injected,
                  :additional_mrnas_injected,
                  :additonal_proteins_injected,
                  :additonal_dye_and_chemicals,
                  :date_born,
                  :time_mounted,
                  :mounting_orientation,
                  :date_screened_initial_feedback,
                  :date_imaged,
                  :data_location,
                  :female_plasmid_base_code,
                  :female_allele,
                  :male_plasmid_base_code,
                  :male_allele,
                  :additional_plasmids_plasmid_base_code,
                  :additional_mrnas_plasmid_base_code
                )
                RETURNING id
                """
            )

            upsert_roi_sql = text(
                """
                INSERT INTO public.imaging_rois (
                  raw_id,
                  fish_id,
                  fish_label,
                  roi_index,
                  roi_name,
                  roi_dir,
                  dataset,
                  experiment_name,
                  data_location,
                  mount_row_index_scored,
                  mount_id,
                  date_experiment,
                  date_mount,
                  date_born,
                  time_mounted,
                  mounting_orientation,
                  date_screened_initial_feedback,
                  date_imaged
                )
                VALUES (
                  :raw_id,
                  NULL,
                  :fish_label,
                  :roi_index,
                  :roi_name,
                  :roi_dir,
                  :dataset,
                  :experiment_name,
                  :data_location,
                  :mount_row_index_scored,
                  :mount_id,
                  :date_experiment,
                  :date_mount,
                  :date_born,
                  :time_mounted,
                  :mounting_orientation,
                  :date_screened_initial_feedback,
                  :date_imaged
                )
                ON CONFLICT (fish_label, roi_index, dataset)
                DO UPDATE SET
                  raw_id = EXCLUDED.raw_id,
                  roi_name = EXCLUDED.roi_name,
                  roi_dir = EXCLUDED.roi_dir,
                  experiment_name = EXCLUDED.experiment_name,
                  data_location = EXCLUDED.data_location,
                  mount_row_index_scored = EXCLUDED.mount_row_index_scored,
                  mount_id = EXCLUDED.mount_id,
                  date_experiment = EXCLUDED.date_experiment,
                  date_mount = EXCLUDED.date_mount,
                  date_born = EXCLUDED.date_born,
                  time_mounted = EXCLUDED.time_mounted,
                  mounting_orientation = EXCLUDED.mounting_orientation,
                  date_screened_initial_feedback = EXCLUDED.date_screened_initial_feedback,
                  date_imaged = EXCLUDED.date_imaged
                """
            )

            for _, row in rows.iterrows():
                params_raw = {
                    "date_experiment": row.get("date_experiment"),
                    "fish_label": row.get("fish_label"),
                    "roi_rel": row.get("roi_rel"),
                    "roi_name": row.get("roi_name"),
                    "roi_tiffs": int(row["roi_tiffs"]) if not pd.isna(row.get("roi_tiffs")) else None,
                    "roi_dir": row.get("roi_dir"),
                    "dataset": row.get("dataset"),
                    "experiment_name": row.get("experiment_name"),
                    "mount_row_index_scored": int(row["mount_row_index_scored"]) if not pd.isna(row.get("mount_row_index_scored")) else None,
                    "date_mount": row.get("date_mount"),
                    "mount_id": row.get("mount_id"),
                    "zf_female_genotype": row.get("zf_female_genotype"),
                    "zf_male_genotype": row.get("zf_male_genotype"),
                    "additional_plasmids_injected": row.get("additional_plasmids_injected"),
                    "additional_mrnas_injected": row.get("additional_mrnas_injected"),
                    "additonal_proteins_injected": row.get("additonal_proteins_injected"),
                    "additonal_dye_and_chemicals": row.get("additonal_dye_and_chemicals"),
                    "date_born": row.get("date_born"),
                    "time_mounted": row.get("time_mounted"),
                    "mounting_orientation": row.get("mounting_orientation"),
                    "date_screened_initial_feedback": row.get("date_screened_initial_feedback"),
                    "date_imaged": row.get("date_imaged"),
                    "data_location": row.get("data_location"),
                    "female_plasmid_base_code": row.get("female_plasmid_base_code"),
                    "female_allele": row.get("female_allele"),
                    "male_plasmid_base_code": row.get("male_plasmid_base_code"),
                    "male_allele": row.get("male_allele"),
                    "additional_plasmids_plasmid_base_code": row.get("additional_plasmids_plasmid_base_code"),
                    "additional_mrnas_plasmid_base_code": row.get("additional_mrnas_plasmid_base_code"),
                }

                raw_id = cx.execute(insert_raw_sql, params_raw).scalar_one()

                roi_index = parse_roi_index(
                    row.get("roi_rel"),
                    row.get("roi_name"),
                )

                params_roi = {
                    "raw_id": raw_id,
                    "fish_label": row.get("fish_label"),
                    "roi_index": roi_index,
                    "roi_name": row.get("roi_name"),
                    "roi_dir": row.get("roi_dir"),
                    "dataset": row.get("dataset"),
                    "experiment_name": row.get("experiment_name"),
                    "data_location": row.get("data_location"),
                    "mount_row_index_scored": int(row["mount_row_index_scored"]) if not pd.isna(row.get("mount_row_index_scored")) else None,
                    "mount_id": row.get("mount_id"),
                    "date_experiment": row.get("date_experiment"),
                    "date_mount": row.get("date_mount"),
                    "date_born": row.get("date_born"),
                    "time_mounted": row.get("time_mounted"),
                    "mounting_orientation": row.get("mounting_orientation"),
                    "date_screened_initial_feedback": row.get("date_screened_initial_feedback"),
                    "date_imaged": row.get("date_imaged"),
                }

                result = cx.execute(upsert_roi_sql, params_roi)
                inserted += result.rowcount

        st.success(f"Import complete. Inserted/updated {inserted} ROI rows.")