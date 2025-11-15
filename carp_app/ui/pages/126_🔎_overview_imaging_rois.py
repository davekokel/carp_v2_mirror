from __future__ import annotations

import sys
import pathlib

import pandas as pd
import streamlit as st
from sqlalchemy import text

# ---- path/bootstrap ---------------------------------------------------------
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

# ---- dataset / experiment summary (still from imaging_rois) -----------------
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

st.subheader("Dataset / experiment summary")
st.dataframe(ds_df, use_container_width=True)

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

# ---- main query from v_roi_overview -----------------------------------------
query_sql = f"""
SELECT
  ir.imaging_roi_id        AS id,
  ir.dataset,
  ir.experiment_name,
  ir.fish_label,
  ir.fish_id,
  ir.roi_index,
  ir.roi_name,
  ir.roi_dir,
  ir.data_location,
  ir.mount_row_index_scored,
  ir.mount_id,
  ir.date_experiment,
  ir.date_mount,

  ir.inj_plasmid_base_code,
  ir.inj_plasmid_name,
  ir.inj_rna_base_code,
  ir.inj_rna_name,
  ir.inj_dye_base_code,
  ir.inj_dye_name,

  ir.genotype_codes_group,
  ir.allele_names_rollup,
  ir.treatments_codes_group,
  ir.treatments_names_group

FROM public.v_roi_overview ir
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

# ---- main table -------------------------------------------------------------
st.subheader("ROIs")

if not rows:
    st.info("No ROIs matched the current filters.")
else:
    df = pd.DataFrame(rows)

    # Nice column order for visual sanity checking
    preferred_cols = [
        "dataset",
        "experiment_name",
        "fish_label",
        "fish_id",
        "roi_index",
        "roi_name",
        "roi_dir",
        "data_location",
        "mount_row_index_scored",
        "mount_id",
        "date_experiment",
        "date_mount",
        "inj_plasmid_base_code",
        "inj_plasmid_name",
        "inj_rna_base_code",
        "inj_rna_name",
        "inj_dye_base_code",
        "inj_dye_name",
        "genotype_codes_group",
        "allele_names_rollup",
        "treatments_codes_group",
        "treatments_names_group",
        "id",
    ]
    existing_cols = [c for c in preferred_cols if c in df.columns]
    df = df[existing_cols]

    st.dataframe(df, use_container_width=True)

    st.caption(
        "Showing up to "
        f"{len(df) if len(df) < limit else limit} rows "
        "from v_roi_overview with the current filters."
    )