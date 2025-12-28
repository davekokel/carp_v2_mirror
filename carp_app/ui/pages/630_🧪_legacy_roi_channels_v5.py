from __future__ import annotations

import sys
import pathlib
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

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

from carp_app.ui.lib.app_ctx import get_engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Legacy ROI Channels (v5)", page_icon="🧪", layout="wide")
st.title("🧪 Legacy ROI Channels (v5)")

_ENGINE: Engine = get_engine()


@st.cache_data(ttl=60, show_spinner=False)
def _load_roi_paths_display() -> pd.DataFrame:
    q = """
    SELECT
      roi_path,
      tg_display AS "TG",
      fluortag_display AS "FluorTag",
      fluororganelle_display AS "FluorOrganelle",
      date_mount_id,
      genotype_base_codes,
      genotype_allele_codes,
      treatment_rna_base_codes,
      treatment_plasmid_base_codes
    FROM public.v_legacy_roi_path_map_v5_display
    ORDER BY roi_path;
    """
    with _ENGINE.begin() as cx:
        return pd.read_sql(text(q), cx)


@st.cache_data(ttl=60, show_spinner=False)
def _load_channels_for_roi(roi_path: str) -> pd.DataFrame:
    q = """
    SELECT
      roi_path,
      channel_name,
      n_tiffs,
      decision_status,
      note
    FROM public.v_legacy_roi_channels_v5_display
    WHERE roi_path = :roi_path
    ORDER BY channel_name;
    """
    with _ENGINE.begin() as cx:
        return pd.read_sql(text(q), cx, params={"roi_path": roi_path})


def _apply_channel_edits(df: pd.DataFrame) -> None:
    if df.empty:
        return

    rows = df[["roi_path", "channel_name", "decision_status", "note"]].to_dict(orient="records")

    sql = text("""
    UPDATE public.legacy_roi_channels_v5
    SET
      decision_status = :decision_status,
      note = :note,
      updated_at = now()
    WHERE roi_path = :roi_path
      AND channel_name = :channel_name
    """)
    with _ENGINE.begin() as cx:
        cx.execute(sql, rows)


st.subheader("ROI paths")

rois_disp = _load_roi_paths_display()
if rois_disp.empty:
    st.info("No rows in v_legacy_roi_path_map_v5_display.")
    st.stop()

csv_bytes = rois_disp.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download ROI table (CSV)",
    data=csv_bytes,
    file_name="legacy_roi_paths_v5_display.csv",
    mime="text/csv",
)

if "selected_roi_path_v5" not in st.session_state:
    st.session_state.selected_roi_path_v5 = None

event = st.dataframe(
    rois_disp[["roi_path", "TG", "FluorTag", "FluorOrganelle"]],
    width="stretch",
    hide_index=True,
    selection_mode="single-row",
    on_select="rerun",
    height=520,
)

selected: Any = None
try:
    sel_rows = event.selection.rows if event and hasattr(event, "selection") else []
    if sel_rows:
        selected = rois_disp.iloc[sel_rows[0]]["roi_path"]
except Exception:
    selected = None

if selected:
    st.session_state.selected_roi_path_v5 = str(selected)

st.divider()

st.subheader("Channels")

roi_path = st.session_state.get("selected_roi_path_v5")
if not roi_path:
    st.caption("Select an ROI path above to view/edit channels.")
    st.stop()

st.code(roi_path)

ch = _load_channels_for_roi(roi_path)
if ch.empty:
    st.info("No channels found for this roi_path.")
    st.stop()

decision_options = ["undecided", "keep", "kill"]

edited = st.data_editor(
    ch,
    width="stretch",
    hide_index=True,
    num_rows="fixed",
    column_config={
        "roi_path": st.column_config.TextColumn("roi_path", disabled=True),
        "channel_name": st.column_config.TextColumn("channel_name", disabled=True),
        "n_tiffs": st.column_config.NumberColumn("n_tiffs", disabled=True),
        "decision_status": st.column_config.SelectboxColumn("decision_status", options=decision_options, required=True),
        "note": st.column_config.TextColumn("note"),
    },
    key=f"legacy_roi_channels_editor::{roi_path}",
)

c1, c2, _ = st.columns([1, 1, 3])
with c1:
    if st.button("Save changes", type="primary"):
        _apply_channel_edits(edited)
        st.cache_data.clear()
        st.success("Saved.")
with c2:
    if st.button("Reload"):
        st.cache_data.clear()
        st.rerun()
