from __future__ import annotations

import sys
import pathlib
from typing import Dict, Any, List

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

st.set_page_config(
    page_title="CARP — Annotate imaging ROIs",
    page_icon="📝",
    layout="wide",
)

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.title("📝 Annotate imaging ROIs")

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

if not ds_rows:
    st.info("No imaging ROIs found yet. Upload a CSV on the 'upload imaging rois' page first.")
    st.stop()

ds_df = pd.DataFrame(ds_rows)

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

params: Dict[str, Any] = {"limit": int(limit)}
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

with engine().begin() as cx:
    rows = cx.execute(text(query_sql), params).mappings().all()

if not rows:
    st.info("No ROIs matched the current filters.")
    st.stop()

df = pd.DataFrame(rows)

st.subheader("Summary and group filters")

candidate_group_cols = [
    c
    for c in [
        "dataset",
        "experiment_name",
        "treatments_codes_group",
        "treatments_fusions_group",
        "genotype_codes_group",
        "genotype_fusions_group",
        "treatment_vs_genotype_codes",
        "treatment_vs_genotype_fusions",
        "legacy_pair_code",
        "legacy_clutch_code",
    ]
    if c in df.columns
]

group_value_dfs: Dict[str, pd.DataFrame] = {}

if not candidate_group_cols:
    st.info("No fields available to summarize.")
else:
    field_cfg = pd.DataFrame(
        {"field": candidate_group_cols, "include": [False] * len(candidate_group_cols)}
    )
    field_cfg = st.data_editor(
        field_cfg,
        key="annotate_roi_group_fields",
        num_rows="fixed",
        hide_index=True,
        use_container_width=True,
        column_config={
            "field": st.column_config.TextColumn("Group/filter by field", disabled=True),
            "include": st.column_config.CheckboxColumn("Show table", default=False),
        },
    )

    selected_fields = field_cfg.loc[field_cfg["include"], "field"].tolist()

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

            edited_group = st.data_editor(
                base,
                key=f"annotate_roi_group_values_{field}",
                hide_index=True,
                use_container_width=True,
                column_config={
                    "include": st.column_config.CheckboxColumn("Filter on this value", default=False),
                },
            )
            group_value_dfs[field] = edited_group
    else:
        st.info("Select one or more fields above to see and filter by group tables.")

mask_groups = pd.Series(True, index=df.index)

for field, gdf in group_value_dfs.items():
    chosen = gdf.loc[gdf["include"], field].tolist()
    if chosen:
        mask_groups &= df[field].isin(chosen)

df_filtered = df[mask_groups].copy()

st.subheader("Select ROIs to annotate")

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
    "roi_dir",
    "date_experiment",
    "id",
]

if df_filtered.empty:
    st.info("No ROIs after applying group filters.")
    st.stop()

available_cols = [c for c in preferred_cols if c in df_filtered.columns]
if not available_cols:
    available_cols = list(df_filtered.columns)

selected_cols = st.multiselect(
    "Columns to show in ROI table",
    options=available_cols,
    default=available_cols,
    key="annotate_roi_columns",
)

df_table = df_filtered.copy()
df_table.insert(0, "select", False)

table_cols: List[str] = ["select"] + selected_cols
if "id" not in table_cols and "id" in df_table.columns:
    table_cols.append("id")

edited = st.data_editor(
    df_table[table_cols],
    key="annotate_rois_table",
    hide_index=True,
    use_container_width=True,
    column_config={
        "select": st.column_config.CheckboxColumn("Select", default=False),
    },
)

selected_ids: List[str] = []
if "id" in edited.columns:
    selected_ids = edited.loc[edited["select"], "id"].astype(str).tolist()

st.caption(f"{len(selected_ids)} ROIs selected for annotation.")

active_roi_id: str | None = None
if len(selected_ids) == 1:
    active_roi_id = selected_ids[0]
elif len(selected_ids) > 1:
    active_roi_id = selected_ids[0]

st.subheader("Details for selected ROI")

if active_roi_id is None:
    st.info("Select a single ROI (or multiple; the first will be shown here) to see its details.")
else:
    row = df_filtered.loc[df_filtered["id"].astype(str) == active_roi_id]
    if not row.empty:
        row = row.iloc[0]
        pivot = (
            row.astype(str)
            .reset_index()
            .rename(columns={"index": "field", 0: "value"})
        )
        st.dataframe(pivot, use_container_width=True, hide_index=True)

        with engine().begin() as cx:
            single_notes = cx.execute(
                text(
                    """
                    SELECT
                      a.label,
                      a.note_text,
                      a.created_by,
                      a.created_at
                    FROM public.annotations a
                    WHERE a.entity_kind = 'imaging_roi'
                      AND a.entity_id::text = :roi_id
                    ORDER BY a.created_at DESC
                    """
                ),
                {"roi_id": active_roi_id},
            ).mappings().all()

        st.markdown("**Notes for this ROI**")
        if not single_notes:
            st.info("No notes yet for this ROI.")
        else:
            single_df = pd.DataFrame(single_notes)
            st.dataframe(single_df, use_container_width=True, hide_index=True)

st.subheader("Add note to selected ROIs")

note_text = st.text_area("Note", height=120)

creator_default = getattr(user, "email", None) or getattr(user, "id", None) or ""
if "annotate_rois_created_by" not in st.session_state:
    st.session_state["annotate_rois_created_by"] = str(creator_default)

created_by = st.text_input("Created by", key="annotate_rois_created_by")

can_submit = bool(selected_ids) and bool(note_text.strip())

if st.button("Add note", type="primary", disabled=not can_submit):
    note = note_text.strip()
    first_line = note.splitlines()[0] if note else ""
    label = first_line[:80] if first_line else "ROI note"
    with engine().begin() as cx:
        for roi_id in selected_ids:
            cx.execute(
                text(
                    """
                    INSERT INTO public.annotations (kind_code, label, entity_kind, entity_id, note_text, created_by)
                    VALUES ('roi_note', :label, 'imaging_roi', :entity_id, :note_text, :created_by)
                    """
                ),
                {
                    "label": label,
                    "entity_id": roi_id,
                    "note_text": note,
                    "created_by": created_by or None,
                },
            )
    st.success(f"Added note to {len(selected_ids)} ROIs.")

st.subheader("Existing notes for filtered ROIs")

roi_ids = df_filtered["id"].astype(str).tolist()

notes_rows: List[Dict[str, Any]] = []
if roi_ids:
    with engine().begin() as cx:
        notes_rows = cx.execute(
            text(
                """
                SELECT
                  a.entity_id AS roi_id,
                  a.label,
                  a.note_text,
                  a.created_by,
                  a.created_at
                FROM public.annotations a
                WHERE a.entity_kind = 'imaging_roi'
                  AND a.entity_id::text = ANY(:roi_ids)
                ORDER BY a.created_at DESC
                """
            ),
            {"roi_ids": roi_ids},
        ).mappings().all()

if not notes_rows:
    st.info("No notes found yet for the current ROI selection.")
else:
    notes_df = pd.DataFrame(notes_rows)
    meta_df = df_filtered[["id", "dataset", "experiment_name", "fish_label", "roi_index", "roi_name"]]
    meta_df = meta_df.rename(columns={"id": "roi_id"})
    notes_df = notes_df.merge(meta_df, on="roi_id", how="left")
    notes_df = notes_df[
        [
            "created_at",
            "created_by",
            "label",
            "note_text",
            "dataset",
            "experiment_name",
            "fish_label",
            "roi_index",
            "roi_name",
            "roi_id",
        ]
    ]
    st.dataframe(notes_df, use_container_width=True, hide_index=True)