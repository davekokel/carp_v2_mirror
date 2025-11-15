from __future__ import annotations

import sys
import pathlib

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

# ---- page config & auth -----------------------------------------------------
st.set_page_config(
    page_title="CARP — Overview imaging ROIs",
    page_icon="📷",
    layout="wide",
)

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.title("📷 Overview imaging ROIs")

# ---- dataset / experiment summary base data ---------------------------------
try:
    with engine().begin() as cx:
        ds_rows = cx.execute(
            text(
                """
                SELECT
                  dataset,
                  experiment_name,
                  count(*) AS n_rois
                FROM public.imaging_rois
                GROUP BY dataset, experiment_name
                ORDER BY dataset, experiment_name
                """
            )
        ).mappings().all()
except Exception as e:
    st.error("Error querying public.imaging_rois")
    st.exception(e)
    st.stop()

if not ds_rows:
    st.info("No imaging ROIs found yet. Upload a CSV on the 'upload imaging rois' page first.")
    st.stop()

ds_df = pd.DataFrame(ds_rows)

# ---- sidebar filters --------------------------------------------------------
st.sidebar.header("Filters")

all_datasets = ["(all)"] + sorted(ds_df["dataset"].dropna().unique().tolist())
dataset_choice = st.sidebar.selectbox("Dataset", all_datasets)

exp_options = ["(all)"]
if dataset_choice != "(all)":
    exp_options += sorted(
        ds_df.loc[ds_df["dataset"] == dataset_choice, "experiment_name"]
        .dropna()
        .unique()
        .tolist()
    )
experiment_choice = st.sidebar.selectbox("Experiment", exp_options)

fish_search = st.sidebar.text_input("Fish label contains", "")
roi_search = st.sidebar.text_input("ROI name contains", "")

limit = st.sidebar.number_input(
    "Max rows",
    min_value=100,
    max_value=5000,
    value=1000,
    step=100,
)

# ---- build WHERE clause -----------------------------------------------------
params: dict[str, object] = {"limit": int(limit)}
where_clauses = ["1=1"]

if dataset_choice != "(all)":
    where_clauses.append("ir.dataset = :dataset")
    params["dataset"] = dataset_choice

if experiment_choice != "(all)":
    where_clauses.append("ir.experiment_name = :experiment_name")
    params["experiment_name"] = experiment_choice

if fish_search.strip():
    where_clauses.append("ir.fish_label ILIKE :fish_search")
    params["fish_search"] = f"%{fish_search.strip()}%"

if roi_search.strip():
    where_clauses.append("ir.roi_name ILIKE :roi_search")
    params["roi_search"] = f"%{roi_search.strip()}%"

where_sql = " AND ".join(where_clauses)

# ---- summary: grouped by treatment_codes > genotype_codes -------------------
summary_sql = f"""
SELECT
  COALESCE(ir.treatments_codes_group, '')          AS treatments_codes_group,
  COALESCE(ir.genotype_codes_group, '')            AS genotype_codes_group,
  COALESCE(ir.treatment_vs_genotype_codes, '')     AS treatment_vs_genotype_codes,
  COALESCE(ir.treatments_fusions_group, '')        AS treatments_fusions_group,
  COALESCE(ir.genotype_fusions_group, '')          AS genotype_fusions_group,
  COALESCE(ir.treatment_vs_genotype_fusions, '')   AS treatment_vs_genotype_fusions,
  count(*) AS n_rois
FROM public.v_roi_overview ir
WHERE {where_sql}
GROUP BY
  COALESCE(ir.treatments_codes_group, ''),
  COALESCE(ir.genotype_codes_group, ''),
  COALESCE(ir.treatment_vs_genotype_codes, ''),
  COALESCE(ir.treatments_fusions_group, ''),
  COALESCE(ir.genotype_fusions_group, ''),
  COALESCE(ir.treatment_vs_genotype_fusions, '')
ORDER BY n_rois DESC, treatment_vs_genotype_codes;
"""

summary_params = {k: v for k, v in params.items() if k != "limit"}

try:
    with engine().begin() as cx:
        summary_rows = cx.execute(text(summary_sql), summary_params).mappings().all()
except Exception as e:
    st.error("Error building treatment/genotype summary from v_roi_overview")
    st.exception(e)
    st.stop()

st.subheader("Treatment vs genotype summary")

summary_df = pd.DataFrame(summary_rows)
if not summary_df.empty:
    summary_cols = [
        "treatments_codes_group",
        "genotype_codes_group",
        "treatment_vs_genotype_codes",
        "treatments_fusions_group",
        "genotype_fusions_group",
        "treatment_vs_genotype_fusions",
        "n_rois",
    ]
    existing_summary = [c for c in summary_cols if c in summary_df.columns]
    summary_df = summary_df[existing_summary]
    st.dataframe(summary_df, width="stretch")
else:
    st.info("No summary rows matched the current filters.")

# ---- dataset / experiment summary -------------------------------------------
st.subheader("Dataset / experiment summary")
st.dataframe(ds_df, width="stretch")

# ---- main query from v_roi_overview -----------------------------------------
query_sql = f"""
SELECT
  ir.imaging_roi_id        AS id,
  ir.dataset,
  ir.experiment_name,
  ir.fish_label,
  ir.roi_index,
  ir.roi_name,
  ir.roi_dir,

  ir.date_mount                               AS legacy_date_mount,
  ir.mount_id                                 AS legacy_mount_id,
  r.zf_female_genotype                        AS legacy_zf_female_genotype,
  r.zf_male_genotype                          AS legacy_zf_male_genotype,
  r.additional_plasmids_injected              AS legacy_additional_plasmids_injected,
  r.additional_mrnas_injected                 AS legacy_additional_mrnas_injected,
  r.additonal_proteins_injected               AS legacy_additonal_proteins_injected,
  r.additonal_dye_and_chemicals               AS legacy_additonal_dye_and_chemicals,
  ir.date_born                                AS legacy_date_born,
  ir.time_mounted                             AS legacy_time_mounted,
  ir.mounting_orientation                     AS legacy_mounting_orientation,
  ir.date_screened_initial_feedback           AS legacy_date_screened_initial_feedback,
  ir.date_imaged                              AS legacy_date_imaged,
  ir.data_location                            AS legacy_data_location,

  ir.legacy_pair_code,
  ir.legacy_clutch_code,

  ir.inj_plasmid_base_code,
  ir.inj_rna_base_code,

  ir.treatments_codes_group,
  ir.genotype_codes_group,
  ir.treatment_vs_genotype_codes,
  ir.treatments_fusions_group,
  ir.genotype_fusions_group,
  ir.treatment_vs_genotype_fusions,

  ir.date_experiment

FROM public.v_roi_overview ir
JOIN raw.imaging_rois_raw r
  ON r.id = ir.raw_id
WHERE {where_sql}
ORDER BY ir.dataset, ir.experiment_name, ir.fish_label, ir.roi_index
LIMIT :limit
"""

try:
    with engine().begin() as cx:
        rows = cx.execute(text(query_sql), params).mappings().all()
except Exception as e:
    st.error("Error loading ROI rows from public.v_roi_overview")
    st.exception(e)
    st.stop()

# ---- main table + download --------------------------------------------------
st.subheader("ROIs")

if not rows:
    st.info("No ROIs matched the current filters.")
else:
    df = pd.DataFrame(rows)

    preferred_cols = [
        # 14 legacy fields first, in the requested order
        "legacy_date_mount",
        "legacy_mount_id",
        "legacy_zf_female_genotype",
        "legacy_zf_male_genotype",
        "legacy_additional_plasmids_injected",
        "legacy_additional_mrnas_injected",
        "legacy_additonal_proteins_injected",
        "legacy_additonal_dye_and_chemicals",
        "legacy_date_born",
        "legacy_time_mounted",
        "legacy_mounting_orientation",
        "legacy_date_screened_initial_feedback",
        "legacy_date_imaged",
        "legacy_data_location",
        # core identity
        "dataset",
        "experiment_name",
        "fish_label",
        "roi_index",
        "roi_name",
        # legacy pair/clutch + codes/fusions
        "legacy_pair_code",
        "legacy_clutch_code",
        "inj_plasmid_base_code",
        "inj_rna_base_code",
        "treatments_codes_group",
        "genotype_codes_group",
        "treatment_vs_genotype_codes",
        "treatments_fusions_group",
        "genotype_fusions_group",
        "treatment_vs_genotype_fusions",
        # misc
        "roi_dir",
        "date_experiment",
        "id",
    ]
    existing = [c for c in preferred_cols if c in df.columns]
    df = df[existing]

    st.dataframe(df, width="stretch")

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered ROIs as CSV",
        data=csv_bytes,
        file_name="roi_overview_filtered.csv",
        mime="text/csv",
    )

    st.caption(
        "Showing "
        f"{len(df)} rows (limit {limit}) "
        "from v_roi_overview with the current filters."
    )