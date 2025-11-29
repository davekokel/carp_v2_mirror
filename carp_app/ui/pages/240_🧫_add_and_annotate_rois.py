from __future__ import annotations

import sys
import pathlib
from datetime import datetime, date
from typing import Optional, Dict, Any, List

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── repo bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine as _engine  # core hook


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🧫 Add & annotate ROIs",
    page_icon="🧫",
    layout="wide",
)
st.title("🧫 Add & annotate ROIs (v11 imaging)")

V_ROI_OVERVIEW = "public.v_roi_overview"


# ───────── engine ─────────
def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _exists_view(qualified: str) -> bool:
    s, n = qualified.split(".", 1)
    with eng().begin() as cx:
        r = pd.read_sql(
            text(
                """
          SELECT 1 FROM information_schema.views
          WHERE table_schema = :s AND table_name = :n
          UNION ALL
          SELECT 1 FROM pg_catalog.pg_matviews
          WHERE schemaname = :s AND matviewname = :n
          LIMIT 1
        """
            ),
            cx,
            params={"s": s, "n": n},
        )
    return not r.empty


# sanity: require v_roi_overview to exist
if not _exists_view(V_ROI_OVERVIEW):
    st.error(
        f"Required view {V_ROI_OVERVIEW} not found. "
        "Create v_roi_overview (plate_code, slot_label, roi_key, fish_code/clutch_code, etc.) "
        "before using this page."
    )
    st.stop()


# ════════════════════════════════════════════════════════
# SECTION 1 — FILTER & LOAD ROIs
# ════════════════════════════════════════════════════════
st.subheader("Step 1 — Filter ROIs", anchor=False)

with st.form("roi_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 0.7])
    with c1:
        q_raw = st.text_input(
            "Search (plate / slot / roi_key / fish_code / clutch_code / genotype)",
            "",
        )
    with c2:
        plate_raw = st.text_input("Plate code contains (optional)", "")
    with c3:
        date_raw = st.text_input("Experiment date = (YYYY-MM-DD, optional)", "")
    with c4:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=500,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply", key="roi_filters_apply")

q = _norm(q_raw)
plate_filter = _norm(plate_raw)
date_filter: Optional[date] = None

if date_raw:
    try:
        date_filter = datetime.strptime(date_raw, "%Y-%m-%d").date()
    except ValueError:
        st.warning("Experiment date must be YYYY-MM-DD if provided.")
        st.stop()

where: List[str] = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  plate_code        ILIKE :ql"
        " OR slot_label      ILIKE :ql"
        " OR roi_key         ILIKE :ql"
        " OR COALESCE(fish_code,'')   ILIKE :ql"
        " OR COALESCE(clutch_code,'') ILIKE :ql"
        " OR COALESCE(genotype_pretty,'') ILIKE :ql"
        ")"
    )

if plate_filter:
    params["plate_like"] = f"%{plate_filter}%"
    where.append("plate_code ILIKE :plate_like")

if date_filter:
    params["exp_date"] = date_filter.isoformat()
    # assuming view exposes experiment_date
    where.append("experiment_date = :exp_date")

where_sql = " AND ".join(where)

# We assume a canonical v_roi_overview that includes these fields.
sql_rois = text(
    f"""
    SELECT
      roi_id::text                 AS roi_id,
      roi_key,
      plate_code,
      slot_label,
      experiment_date,
      fish_code,
      clutch_code,
      parents_label,
      genotype_pretty,
      birthday,
      genetic_background,
      all_marker_fluor_codes,
      data_path,
      plate_id_filled,
      slot_id_filled
    FROM {V_ROI_OVERVIEW}
    WHERE {where_sql}
    ORDER BY experiment_date DESC NULLS LAST,
             plate_code,
             slot_label,
             roi_key
    LIMIT :lim;
"""
)

try:
    with eng().begin() as cx:
        df_rois = pd.read_sql(sql_rois, cx, params=params)
except Exception as e:
    st.error(
        f"Error querying {V_ROI_OVERVIEW}. "
        f"Check that the view exists and exposes the expected columns. "
        f"Details: {type(e).__name__}: {e}"
    )
    st.stop()

for c in df_rois.select_dtypes(include=["object", "string"]).columns:
    df_rois[c] = df_rois[c].astype("string").fillna("")

st.caption(f"{len(df_rois)} ROI row(s)")

if df_rois.empty:
    st.info("No ROIs match the current filters.")
    st.stop()

# Core ROI fields in the main table
view = df_rois.copy()
view.insert(0, "✓ Select", False)

main_cols = [
    "✓ Select",
    "roi_key",
    "plate_code",
    "slot_label",
    "fish_code",
    "clutch_code",
    "genotype_pretty",
    "all_marker_fluor_codes",
    "experiment_date",
]
main_cols = [c for c in main_cols if c in view.columns]

grid = st.data_editor(
    view[main_cols],
    key="rois_overview_core",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "roi_key": st.column_config.TextColumn("ROI key", disabled=True),
        "plate_code": st.column_config.TextColumn("Plate", disabled=True),
        "slot_label": st.column_config.TextColumn("Slot", disabled=True),
        "fish_code": st.column_config.TextColumn("Fish code", disabled=True),
        "clutch_code": st.column_config.TextColumn("Clutch code", disabled=True),
        "genotype_pretty": st.column_config.TextColumn(
            "Genotype", disabled=True, width="large"
        ),
        "all_marker_fluor_codes": st.column_config.TextColumn(
            "Markers", disabled=True, width="large"
        ),
        "experiment_date": st.column_config.DateColumn(
            "Experiment date", disabled=True
        ),
    },
)

st.download_button(
    "⬇︎ Download ROI overview (CSV)",
    data=df_rois.to_csv(index=False).encode("utf-8"),
    file_name="roi_overview.csv",
    type="secondary",
    mime="text/csv",
)

# ════════════════════════════════════════════════════════
# SECTION 2 — DRILL-DOWN & ANNOTATION EDITOR
# ════════════════════════════════════════════════════════
st.divider()
st.subheader("Step 2 — Annotate selected ROIs", anchor=False)

sel_idxs: List[int] = []
if "✓ Select" in grid.columns:
    sel_idxs = grid.index[grid["✓ Select"] == True].to_series().tolist()

if not sel_idxs:
    st.caption("Select one or more ROIs above to annotate.")
    st.stop()

selected = df_rois.iloc[sel_idxs].reset_index(drop=True)
st.caption(f"Selected ROIs: {len(selected)}")

# Build an annotation table. We’re not reading from imaging_roi_annotations yet;
# this is a planning/export UI. Columns are intentionally generic:
# roi_key, plate_code, slot_label, label, organelle, notes, qc_flag.
anno_rows: List[Dict[str, Any]] = []
for _, r in selected.iterrows():
    anno_rows.append(
        {
            "roi_id": r.get("roi_id"),
            "roi_key": r.get("roi_key"),
            "plate_code": r.get("plate_code"),
            "slot_label": r.get("slot_label"),
            "fish_code": r.get("fish_code"),
            "clutch_code": r.get("clutch_code"),
            "genotype_pretty": r.get("genotype_pretty"),
            # annotation fields (editable)
            "annotation_label": "",
            "annotation_organelle": "",
            "annotation_notes": "",
            "qc_flag": "",
        }
    )

df_anno = pd.DataFrame(anno_rows)

st.markdown(
    "Fill in **annotation_label**, **annotation_organelle**, **annotation_notes**, "
    "and **qc_flag** as needed. This table is not yet persisted; export to CSV "
    "and feed into your ROI annotation loader."
)

edited = st.data_editor(
    df_anno,
    key="roi_annotation_editor",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "roi_id": st.column_config.TextColumn("roi_id", disabled=True),
        "roi_key": st.column_config.TextColumn("ROI key", disabled=True),
        "plate_code": st.column_config.TextColumn("Plate", disabled=True),
        "slot_label": st.column_config.TextColumn("Slot", disabled=True),
        "fish_code": st.column_config.TextColumn("Fish code", disabled=True),
        "clutch_code": st.column_config.TextColumn("Clutch code", disabled=True),
        "genotype_pretty": st.column_config.TextColumn(
            "Genotype", disabled=True, width="large"
        ),
        "annotation_label": st.column_config.TextColumn(
            "Annotation label", disabled=False, width="large"
        ),
        "annotation_organelle": st.column_config.TextColumn(
            "Organelle", disabled=False
        ),
        "annotation_notes": st.column_config.TextColumn(
            "Notes", disabled=False, width="large"
        ),
        "qc_flag": st.column_config.TextColumn("QC flag", disabled=False),
    },
)

st.download_button(
    "⬇︎ Download ROI annotations (CSV)",
    data=edited.to_csv(index=False).encode("utf-8"),
    file_name="roi_annotations_plan.csv",
    type="primary",
    mime="text/csv",
    use_container_width=True,
)

st.info(
    "This page currently produces an ROI annotation CSV only. "
    "Once imaging_roi_annotations schema and write semantics are finalized, "
    "this will be the place to insert/update annotation rows in the DB."
)