from __future__ import annotations

import sys
import pathlib
import re
from datetime import date
from typing import Optional

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

st.set_page_config(page_title="CARP — Legacy ROI Channels (v5, flat)", page_icon="🧪", layout="wide")
st.title("🧪 Legacy ROI Channels (v5) — flat")

_ENGINE: Engine = get_engine()

_DATE8_RX = re.compile(r"(20\d{6})")
_HPF_RX = re.compile(r"(\d{1,4})\s*hpf", re.I)


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


def _contains(s: str, needle: str) -> bool:
    if not needle:
        return True
    return needle.lower() in (s or "").lower()


def _roi_date(roi_path: str) -> Optional[date]:
    s = str(roi_path or "")
    m = _DATE8_RX.search(s)
    if not m:
        return None
    ymd = m.group(1)
    try:
        y = int(ymd[0:4])
        mo = int(ymd[4:6])
        d = int(ymd[6:8])
        return date(y, mo, d)
    except Exception:
        return None


flat = _load_flat()
if flat.empty:
    st.info("No rows in v_legacy_roi_channels_v5_display.")
    st.stop()

st.subheader("Filters")

c1, c2, c3, c4 = st.columns([2, 2, 2, 1.5])
with c1:
    roi_q = st.text_input("roi_path contains", value="", placeholder="e.g. 20250808_mem_organelle")
with c2:
    chan_q = st.text_input("channel_name contains", value="", placeholder="e.g. cam, 488, 560, 642")
with c3:
    ds_opts_all = ["undecided", "keep", "kill"]
    ds_sel = st.multiselect("decision_status", options=ds_opts_all, default=ds_opts_all)
with c4:
    min_tiffs = st.number_input("min n_tiffs", min_value=0, value=0, step=1)

c5, c6, c7 = st.columns([2, 2, 2])
with c5:
    date_from = st.date_input("date from (from roi_path)", value=None)
with c6:
    date_to = st.date_input("date to (from roi_path)", value=None)
with c7:
    only_typed_left = st.checkbox("only rows containing ' > '", value=False)

c8, _, _ = st.columns([2, 2, 2])
with c8:
    only_with_note = st.checkbox("only rows with note", value=False)

df = flat.copy()

def _roi_hpf(roi_path: str) -> Optional[int]:
    s = str(roi_path or "")
    m = _HPF_RX.search(s)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

df["imaging_date"] = df["roi_path"].astype(str).map(_roi_date)
df["imaging_age_hpf"] = df["roi_path"].astype(str).map(_roi_hpf)

# hpf -> days (float)
df["imaging_age_days"] = df["imaging_age_hpf"].map(lambda x: (float(x) / 24.0) if x is not None else None)

# birthday may come back as date/datetime; normalize and compute delta-days when possible
bd = pd.to_datetime(df.get("birthday"), errors="coerce")
im = pd.to_datetime(df.get("imaging_date"), errors="coerce")
df["birthday"] = bd.dt.date
df["imaging_age_days_from_birthday"] = (im - bd).dt.days

if roi_q:
    df = df[df["roi_path"].astype(str).map(lambda x: _contains(x, roi_q))]

if chan_q:
    df = df[df["channel_name"].astype(str).map(lambda x: _contains(x, chan_q))]

if ds_sel:
    df = df[df["decision_status"].isin(ds_sel)]
else:
    df = df.iloc[0:0]

if min_tiffs > 0:
    df = df[df["n_tiffs"].fillna(0).astype(int) >= int(min_tiffs)]

if date_from is not None or date_to is not None:
    dser = df["roi_path"].astype(str).map(_roi_date)
    if date_from is not None:
        df = df[dser.notna() & (dser >= date_from)]
        dser = df["roi_path"].astype(str).map(_roi_date)
    if date_to is not None:
        df = df[dser.notna() & (dser <= date_to)]

if only_typed_left:
    def _has_arrow(r: pd.Series) -> bool:
        for k in ["display_basecode", "display_fluortag", "display_fluororganelle"]:
            if " > " in (str(r.get(k) or "")):
                return True
        return False
    df = df[df.apply(_has_arrow, axis=1)]

if only_with_note:
    df = df[df["note"].fillna("").astype(str).str.strip() != ""]

st.divider()

full_csv = flat.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download FULL CSV",
    data=full_csv,
    file_name="legacy_roi_channels_v5_flat_full.csv",
    mime="text/csv",
)

filtered_csv = df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download FILTERED CSV",
    data=filtered_csv,
    file_name="legacy_roi_channels_v5_flat_filtered.csv",
    mime="text/csv",
)

st.divider()

decision_options = ["undecided", "keep", "kill"]

edited = st.data_editor(
    df,
    width="stretch",
    height=1100,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "roi_path": st.column_config.TextColumn("roi_path", disabled=True, width="large"),
        "display_basecode": st.column_config.TextColumn("TG", disabled=True, width="large"),
        "display_fluortag": st.column_config.TextColumn("FluorTag", disabled=True, width="large"),
        "display_fluororganelle": st.column_config.TextColumn("FluorOrganelle", disabled=True, width="large"),
        "orientation": st.column_config.TextColumn("orientation", disabled=True, width="small"),
        "birthday": st.column_config.DateColumn("birthday", disabled=True, width="small"),
        "anatomical_location": st.column_config.TextColumn("anatomical_location", disabled=True, width="medium"),
        "imaging_date": st.column_config.DateColumn("imaging_date", disabled=True, width="small"),
        "imaging_age_hpf": st.column_config.NumberColumn("imaging_age_hpf", disabled=True, width="small"),
        "imaging_age_days": st.column_config.NumberColumn("imaging_age_days", disabled=True, width="small"),
        "imaging_age_days_from_birthday": st.column_config.NumberColumn("age_days", disabled=True, width="small"),
        "channel_name": st.column_config.TextColumn("channel_name", disabled=True, width="medium"),
        "n_tiffs": st.column_config.NumberColumn("n_tiffs", disabled=True, width="small"),
        "decision_status": st.column_config.SelectboxColumn("decision_status", options=decision_options, required=True, width="small"),
        "note": st.column_config.TextColumn("note", width="large"),
        "imaging_age_days_from_birthday": st.column_config.NumberColumn("age_days", disabled=True, width="small"),
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
