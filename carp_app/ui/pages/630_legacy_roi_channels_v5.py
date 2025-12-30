from __future__ import annotations

import sys
import pathlib
from typing import Any, Dict

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
def _load_totals_v5() -> Dict[str, Any]:
    q = """
    SELECT
      (SELECT count(*) FROM public.v_legacy_roi_path_map_v5_display) AS roi_paths_rows,
      (SELECT count(*) FROM public.v_legacy_roi_channels_v5_display) AS channel_rows,
      (SELECT count(distinct roi_path) FROM public.v_legacy_roi_channels_v5_display) AS channel_roi_paths
    """
    with _ENGINE.begin() as cx:
        row = cx.execute(text(q)).mappings().first()
        return dict(row or {})


tot = _load_totals_v5()
st.caption(
    f"Totals — ROI paths: {int(tot.get('roi_paths_rows', 0)):,} rows • "
    f"Channels: {int(tot.get('channel_rows', 0)):,} rows across {int(tot.get('channel_roi_paths', 0)):,} roi_path"
)


@st.cache_data(ttl=60, show_spinner=False)
def _load_roi_paths() -> pd.DataFrame:
    q = """
    SELECT
      roi_path,
      tg_display AS display_basecode,
      fluortag_display AS display_fluortag,
      fluororganelle_display AS display_fluororganelle
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
rois = _load_roi_paths()

if rois.empty:
    st.info("No rows in v_legacy_roi_path_map_v5_display.")
    st.stop()

rois_disp = rois[["roi_path", "display_basecode", "display_fluortag", "display_fluororganelle"]].copy()

roi_csv = rois_disp.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download ROI paths CSV",
    data=roi_csv,
    file_name="legacy_roi_paths_v5.csv",
    mime="text/csv",
)

if "selected_roi_path_v5" not in st.session_state:
    st.session_state.selected_roi_path_v5 = None

event = st.dataframe(
    rois_disp,
    width="stretch",
    hide_index=True,
    selection_mode="single-row",
    on_select="rerun",
    height=520,
    column_config={
        "roi_path": st.column_config.TextColumn("roi_path", disabled=True, width="large"),
        "display_basecode": st.column_config.TextColumn("TG", disabled=True, width="large"),
        "display_fluortag": st.column_config.TextColumn("FluorTag", disabled=True, width="large"),
        "display_fluororganelle": st.column_config.TextColumn("FluorOrganelle", disabled=True, width="large"),
    },
)

selected = None
try:
    sel_rows = event.selection.rows if event and hasattr(event, "selection") else []
    if sel_rows:
        selected = rois.iloc[sel_rows[0]]["roi_path"]
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
        "roi_path": st.column_config.TextColumn("roi_path", disabled=True, width="large"),
        "channel_name": st.column_config.TextColumn("channel_name", disabled=True, width="medium"),
        "n_tiffs": st.column_config.NumberColumn("n_tiffs", disabled=True, width="small"),
        "decision_status": st.column_config.SelectboxColumn("decision_status", options=decision_options, required=True, width="small"),
        "note": st.column_config.TextColumn("note", width="large"),
    },
    key=f"legacy_roi_channels_editor::{roi_path}",
)

channels_csv = edited.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download channels CSV",
    data=channels_csv,
    file_name=f"legacy_roi_channels_v5__{roi_path.replace('/','__')}.csv",
    mime="text/csv",
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