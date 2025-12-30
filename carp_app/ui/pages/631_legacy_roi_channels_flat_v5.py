from __future__ import annotations

import sys
import pathlib
import re
from datetime import date
from typing import Optional, Dict, Any

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

# ─────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# ─────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CARP — Legacy ROI Channels (v5, flat)",
    page_icon="🧪",
    layout="wide",
)
st.title("🧪 Legacy ROI Channels (v5) — flat")

# ─────────────────────────────────────────────────────────────
# Engine (MUST be before any DB access)
# ─────────────────────────────────────────────────────────────
_ENGINE: Engine = get_engine()

# ─────────────────────────────────────────────────────────────
# Totals
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _load_totals_flat_v5() -> Dict[str, Any]:
    q = """
    SELECT
      (SELECT count(*) FROM public.v_legacy_roi_channels_v5_display) AS channel_rows,
      (SELECT count(DISTINCT roi_path) FROM public.v_legacy_roi_channels_v5_display) AS channel_roi_paths
    """
    with _ENGINE.begin() as cx:
        row = cx.execute(text(q)).mappings().first()
        return dict(row or {})

tot = _load_totals_flat_v5()
st.caption(
    f"Totals — Channels: {int(tot.get('channel_rows', 0)):,} rows across "
    f"{int(tot.get('channel_roi_paths', 0)):,} roi_path"
)

# ─────────────────────────────────────────────────────────────
# Regex helpers
# ─────────────────────────────────────────────────────────────
_DATE8_RX = re.compile(r"(20\d{6})")
_HPF_RX = re.compile(r"(\d{1,4})\s*hpf", re.I)

# ─────────────────────────────────────────────────────────────
# Data loader
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _load_flat() -> pd.DataFrame:
    q = """
    SELECT
      ch.roi_path,
      m.tg_display             AS display_basecode,
      m.fluortag_display       AS display_fluortag,
      m.fluororganelle_display AS display_fluororganelle,
      m.orientation,
      m.birthday,
      m.anatomical_location,
      ch.channel_name,
      ch.n_tiffs,
      ch.decision_status,
      ch.note
    FROM public.v_legacy_roi_channels_v5_display ch
    LEFT JOIN public.v_legacy_roi_path_map_v5_display m
      ON m.roi_path = ch.roi_path
    ORDER BY ch.roi_path, ch.channel_name;
    """
    with _ENGINE.begin() as cx:
        return pd.read_sql(text(q), cx)

def _apply_edits(df: pd.DataFrame) -> None:
    if df.empty:
        return

    rows = df[
        ["roi_path", "channel_name", "decision_status", "note"]
    ].to_dict(orient="records")

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

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _contains(s: str, needle: str) -> bool:
    return needle.lower() in (s or "").lower() if needle else True

def _roi_date(roi_path: str) -> Optional[date]:
    m = _DATE8_RX.search(str(roi_path))
    if not m:
        return None
    ymd = m.group(1)
    try:
        return date(int(ymd[0:4]), int(ymd[4:6]), int(ymd[6:8]))
    except Exception:
        return None

def _roi_hpf(roi_path: str) -> Optional[int]:
    m = _HPF_RX.search(str(roi_path))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────
# Load + filters
# ─────────────────────────────────────────────────────────────
flat = _load_flat()
if flat.empty:
    st.info("No rows in v_legacy_roi_channels_v5_display.")
    st.stop()

st.subheader("Filters")

c1, c2, c3, c4 = st.columns([2, 2, 2, 1.5])
with c1:
    roi_q = st.text_input("roi_path contains")
with c2:
    chan_q = st.text_input("channel_name contains")
with c3:
    ds_opts = ["undecided", "keep", "kill"]
    ds_sel = st.multiselect("decision_status", ds_opts, default=ds_opts)
with c4:
    min_tiffs = st.number_input("min n_tiffs", min_value=0, value=0)

df = flat.copy()

df["imaging_date"] = df["roi_path"].map(_roi_date)
df["imaging_age_hpf"] = df["roi_path"].map(_roi_hpf)

if roi_q:
    df = df[df["roi_path"].map(lambda x: _contains(x, roi_q))]
if chan_q:
    df = df[df["channel_name"].map(lambda x: _contains(x, chan_q))]
if ds_sel:
    df = df[df["decision_status"].isin(ds_sel)]
else:
    df = df.iloc[0:0]
if min_tiffs > 0:
    df = df[df["n_tiffs"].fillna(0) >= min_tiffs]

st.caption(f"Filtered — {len(df):,} rows (of {len(flat):,} total)")

st.divider()

# ─────────────────────────────────────────────────────────────
# Downloads
# ─────────────────────────────────────────────────────────────
st.download_button(
    "Download FULL CSV",
    data=flat.to_csv(index=False).encode("utf-8"),
    file_name="legacy_roi_channels_v5_flat_full.csv",
    mime="text/csv",
)

st.download_button(
    "Download FILTERED CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="legacy_roi_channels_v5_flat_filtered.csv",
    mime="text/csv",
)

st.divider()

# ─────────────────────────────────────────────────────────────
# Editor
# ─────────────────────────────────────────────────────────────
edited = st.data_editor(
    df,
    width="stretch",
    height=1000,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "roi_path": st.column_config.TextColumn("roi_path", disabled=True),
        "display_basecode": st.column_config.TextColumn("TG", disabled=True),
        "display_fluortag": st.column_config.TextColumn("FluorTag", disabled=True),
        "display_fluororganelle": st.column_config.TextColumn("FluorOrganelle", disabled=True),
        "channel_name": st.column_config.TextColumn("channel_name", disabled=True),
        "n_tiffs": st.column_config.NumberColumn("n_tiffs", disabled=True),
        "decision_status": st.column_config.SelectboxColumn(
            "decision_status", options=["undecided", "keep", "kill"], required=True
        ),
        "note": st.column_config.TextColumn("note"),
    },
    key="legacy_roi_channels_flat_editor_v5",
)

c1b, c2b, _ = st.columns([1, 1, 6])
with c1b:
    if st.button("Save changes", type="primary"):
        _apply_edits(edited)
        st.cache_data.clear()
        st.success("Saved.")
with c2b:
    if st.button("Reload"):
        st.cache_data.clear()
        st.rerun()