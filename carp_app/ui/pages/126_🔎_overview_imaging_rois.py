# carp_app/ui/pages/???_📷_overview_imaging_rois.py
from __future__ import annotations

import sys
import pathlib
import re

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

# ---- dataset / experiment summary base (for filters + existence check) ------
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

# ---- build WHERE clause for base ROI query ----------------------------------
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

# ---- main ROI query from v_roi_overview + imaging_rois ----------------------
query_sql = f"""
SELECT
  ir.imaging_roi_id        AS id,
  ir.dataset,
  ir.experiment_name,
  ir.fish_label,
  ir.roi_index,
  ir.roi_name,
  ir.roi_dir,

  -- legacy-ish scalar fields from imaging_rois
  iro.date_mount                               AS legacy_date_mount,
  iro.mount_id                                 AS legacy_mount_id,
  iro.zf_female_genotype                       AS legacy_zf_female_genotype,
  iro.zf_male_genotype                         AS legacy_zf_male_genotype,
  iro.additional_plasmids_injected             AS legacy_additional_plasmids_injected,
  iro.additional_mrnas_injected                AS legacy_additional_mrnas_injected,
  iro.additonal_proteins_injected              AS legacy_additonal_proteins_injected,
  iro.additonal_dye_and_chemicals              AS legacy_additonal_dye_and_chemicals,
  iro.date_born                                AS legacy_date_born,
  iro.time_mounted                             AS legacy_time_mounted,
  iro.mounting_orientation                     AS legacy_mounting_orientation,
  iro.date_screened_initial_feedback           AS legacy_date_screened_initial_feedback,
  iro.date_imaged                              AS legacy_date_imaged,
  iro.data_location                            AS legacy_data_location,

  -- genotype / treatment / fluor rollups from the view
  ir.inj_plasmid_base_code,
  ir.inj_rna_base_code,
  ir.genotype_alleles_rollup,
  ir.allele_names_rollup,
  ir.treatments_codes_group,
  ir.treatments_names_group,
  ir.fluors_rollup,

  ir.date_experiment

FROM public.v_roi_overview ir
JOIN public.imaging_rois iro
  ON iro.id = ir.imaging_roi_id
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

if not rows:
    st.info("No ROIs matched the current filters.")
    st.stop()

df = pd.DataFrame(rows)
def _split_tokens(value: object) -> list[str]:
    """
    Split a string on commas/semicolons, trim, drop blanks and literal 'NaN'.
    """
    if value is None:
        return []
    tokens: list[str] = []
    for t in re.split(r"[;,]", str(value)):
        t = t.strip()
        if not t or t.lower() == "nan":
            continue
        tokens.append(t)
    return tokens

def _build_fluors_rollup(row: pd.Series) -> str:
    """
    TRUE fusions only: use genotype_fusions_rollup.
    (These are the genotype-side fusion descriptors.)
    """
    tokens = _split_tokens(row.get("genotype_fusions_rollup"))
    seen = set()
    uniq: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return "; ".join(uniq)

def _build_markers_rollup(row: pd.Series) -> str:
    """
    All fluorescent markers:
    genotype fusions + treatment/dye names (from treatments_names_group).
    """
    tokens: list[str] = []
    for col in ("genotype_fusions_rollup", "treatments_names_group"):
        tokens.extend(_split_tokens(row.get(col)))
    seen = set()
    uniq: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return "; ".join(uniq)

# Build the two rollup fields
df["fluors_rollup"] = df.apply(_build_fluors_rollup, axis=1)
df["markers_rollup"] = df.apply(_build_markers_rollup, axis=1)

if "genotype_fusions_rollup" in df.columns or "treatments_names_group" in df.columns:
    df["fluors_rollup"] = df.apply(_build_fluors_rollup, axis=1)
# ---- summary / group filters (drive ROI table below) ------------------------
st.subheader("Summary and group filters")

candidate_group_cols = [
    c
    for c in [
        "dataset",
        "experiment_name",
        "genotype_alleles_rollup",
        "allele_names_rollup",
        "treatments_codes_group",
        "treatments_names_group",
        "fluors_rollup",    # true fusions (genotype)
        "markers_rollup",   # all markers: genotype + treatments/dyes
    ]
    if c in df.columns
]

if not candidate_group_cols:
    st.info("No fields available to summarize.")
    group_value_dfs: dict[str, pd.DataFrame] = {}
else:
    field_cfg = pd.DataFrame(
        {"field": candidate_group_cols, "include": [False] * len(candidate_group_cols)}
    )
    field_cfg = st.data_editor(
        field_cfg,
        key="roi_group_fields",
        num_rows="fixed",
        hide_index=True,
        use_container_width=True,
        column_order=["include", "field"],
        column_config={
            "field": st.column_config.TextColumn("Group/filter by field", disabled=True),
            "include": st.column_config.CheckboxColumn("Show table", default=False),
        },
    )

    selected_fields = field_cfg.loc[field_cfg["include"], "field"].tolist()

    group_value_dfs: dict[str, pd.DataFrame] = {}
    if selected_fields:
        id_col = "id"
        for field in selected_fields:
            agg_spec = {"n_rois": (id_col, "size")}
            if "dataset" in df.columns:
                agg_spec["n_datasets"] = ("dataset", pd.Series.nunique)
            if "experiment_name" in df.columns:
                agg_spec["n_experiments"] = ("experiment_name", pd.Series.nunique)

            base = (
                df.groupby(field, dropna=False)
                .agg(**agg_spec)
                .reset_index()
                .sort_values("n_rois", ascending=False)
            )
            base.insert(0, "include", False)

            st.markdown(f"##### Groups for `{field}`")
            edited = st.data_editor(
                base,
                key=f"roi_group_values_{field}",
                hide_index=True,
                use_container_width=True,
                column_config={
                    "include": st.column_config.CheckboxColumn("Filter on this value", default=False),
                },
            )
            group_value_dfs[field] = edited
    else:
        st.info("Select one or more fields above to see and filter by group tables.")

# build mask from selected group values
mask_groups = pd.Series(True, index=df.index)

for field, gdf in group_value_dfs.items():
    chosen = gdf.loc[gdf["include"], field].tolist()
    if chosen:
        mask_groups &= df[field].isin(chosen)

df_filtered = df[mask_groups].copy()

# ---- ROI table + download ---------------------------------------------------
st.subheader("ROIs")

preferred_cols = [
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
    "dataset",
    "experiment_name",
    "fish_label",
    "roi_index",
    "roi_name",
    "inj_plasmid_base_code",
    "inj_rna_base_code",
    "genotype_alleles_rollup",
    "allele_names_rollup",
    "treatments_codes_group",
    "treatments_names_group",
    "fluors_rollup",
    "markers_rollup",
    "roi_dir",
    "date_experiment",
    "id",
]
existing = [c for c in preferred_cols if c in df_filtered.columns]
df_display = df_filtered[existing] if existing else df_filtered

st.dataframe(df_display, width="stretch")

csv_bytes = df_display.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download filtered ROIs as CSV",
    data=csv_bytes,
    file_name="roi_overview_filtered.csv",
    mime="text/csv",
)

st.caption(
    "Showing "
    f"{len(df_display)} rows (limit {limit}) "
    "from v_roi_overview + imaging_rois with the current filters and group selections."
)