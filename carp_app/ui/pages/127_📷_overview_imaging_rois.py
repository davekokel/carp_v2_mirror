# carp_app/ui/pages/126_📷_overview_imaging_rois.py
from __future__ import annotations

import os
import sys
import pathlib
from typing import Optional, List

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ---- path/auth bootstrap ----------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:  # pragma: no cover
    def require_app_unlock() -> None:
        ...

from carp_app.ui.lib.page_engine import engine as _engine

# ---- auth / page ------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 📷 Overview imaging ROIs",
    page_icon="📷",
    layout="wide",
)
st.title("📷 Overview imaging ROIs")

# ---- engine helper ----------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL is not set; cannot connect to database.")
        st.stop()
    return _engine()

def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None

# ---- filters -----------------------------------------------------------------
with st.form("roi_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 2, 1])

    with c1:
        q_raw = st.text_input(
            "Search (ROI / path / fish / plate / slot)",
            "",
            help="Matches ROI name, data path, ROI dir, fish_code, plate_code, slot_label.",
        )
    with c2:
        # We don't yet have a dataset column on v_roi_overview; could add later.
        plate_filter = st.text_input(
            "Plate filter (optional, substring match on plate_code)",
            "",
        )
    with c3:
        lim = int(
            st.number_input(
                "Row limit",
                min_value=100,
                max_value=5000,
                value=1000,
                step=100,
            )
        )

    submitted = st.form_submit_button("Apply", use_container_width=True)

q = _norm(q_raw)
plate_q = _norm(plate_filter)
ql = f"%{q}%" if q else None
pl = f"%{plate_q}%" if plate_q else None

# ---- query v_roi_overview ----------------------------------------------------
sql = text(
    """
    SELECT
      imaging_roi_id AS id,
      plate_code,
      slot_label,
      roi_index,
      roi_name,
      roi_dir,
      data_path,
      fish_code,
      fish_nickname,
      birthday,
      genetic_background,
      line_building_stage,
      roi_notes,
      roi_created_at
    FROM public.v_roi_overview
    WHERE
      (:plate_q IS NULL OR plate_code ILIKE :pl)
      AND (
        :q IS NULL
        OR plate_code ILIKE :ql
        OR slot_label ILIKE :ql
        OR roi_name ILIKE :ql
        OR roi_dir ILIKE :ql
        OR data_path ILIKE :ql
        OR fish_code ILIKE :ql
        OR fish_nickname ILIKE :ql
      )
    ORDER BY
      plate_code,
      slot_label,
      roi_index
    LIMIT :lim
    """
)

params = {
    "q": q,
    "ql": ql,
    "plate_q": plate_q,
    "pl": pl,
    "lim": lim,
}

with get_engine().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} ROI row(s) from v_roi_overview (limit {lim})")

if df.empty:
    st.info("No ROIs matched the current filters.")
    st.stop()

# ---- add selection column ----------------------------------------------------
ro = df.copy()
ro.insert(0, "✓ Select", False)

column_config = {
    "id":                st.column_config.TextColumn("ROI ID", disabled=True),
    "plate_code":        st.column_config.TextColumn("Plate", disabled=True),
    "slot_label":        st.column_config.TextColumn("Slot", disabled=True),
    "roi_index":         st.column_config.NumberColumn("ROI #", format="%d", disabled=True),
    "roi_name":          st.column_config.TextColumn("ROI name", disabled=True),
    "roi_dir":           st.column_config.TextColumn("ROI dir", disabled=True),
    "data_path":         st.column_config.TextColumn("Data path", disabled=True),
    "fish_code":         st.column_config.TextColumn("Fish code", disabled=True),
    "fish_nickname":     st.column_config.TextColumn("Fish nickname", disabled=True),
    "birthday":          st.column_config.DateColumn("DOB", disabled=True),
    "genetic_background": st.column_config.TextColumn("Background", disabled=True),
    "line_building_stage": st.column_config.TextColumn("Line stage", disabled=True),
    "roi_notes":         st.column_config.TextColumn("ROI notes", disabled=True),
    "roi_created_at":    st.column_config.DatetimeColumn("Created at", disabled=True),
    "✓ Select":          st.column_config.CheckboxColumn("✓ Select"),
}

ro_view = st.data_editor(
    ro,
    key="imaging_rois_overview",
    use_container_width=True,
    hide_edges=True,
    hide_index=True,
    column_config=column_config,
    column_order=list(column_config.keys()),
)

# track selection
selected_ids: List[str] = []
if isinstance(ro_view, pd.DataFrame) and "✓ Select" in ro_view.columns:
    selected_ids = (
        ro_view.loc[ro_view["✓ Select"] == True, "id"]
        .astype(str)
        .tolist()
    )

st.divider()
st.subheader("Selection & export")

c1, c2 = st.columns([2, 1])
with c1:
    st.caption("1) Select one or more ROI rows above using the ✓ column.")
with c2:
    st.metric("Selected ROIs", len(selected_ids))

# prepare export
export_scope = st.radio(
    "Export scope",
    options=["All rows in table", "Only selected rows"],
    horizontal=True,
)

if export_scope == "Only selected rows" and selected_ids:
    to_export = df[df["id"].astype(str).isin(selected_ids)].copy()
elif export_scope == "Only selected rows":
    st.info("No rows selected; exporting all rows instead.")
    to_export = df.copy()
else:
    to_export = df.copy()

csv_bytes = to_export.to_csv(index=False).encode("utf-8")

st.download_button(
    "⬇︎ Download CSV",
    data=csv_bytes,
    file_name="imaging_rois_overview.csv",
    type="secondary",
    use_container_width=True,
)