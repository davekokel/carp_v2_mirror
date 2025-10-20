from __future__ import annotations
import os
from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine

st.set_page_config(page_title="🔎 Overview Mounts", page_icon="🔎", layout="wide")
st.title("🔎 Overview Mounts")

ENG = get_engine()

def _load_mounts_for_day(d: date) -> pd.DataFrame:
    """
    Use normalized bruker_mount columns. (Legacy mount_date/mount_time removed.)
    """
    sql = text("""
        select
          bm.clutch_instance_id,
          bm.mount_code,
          bm.mounting_orientation,
          bm.n_top,
          bm.n_bottom,
          bm.time_mounted
        from public.bruker_mount bm
        where (bm.time_mounted at time zone 'UTC')::date = :d
        order by bm.time_mounted desc nulls last
    """)
    with ENG.begin() as cx:
        df = pd.read_sql(sql, cx, params={"d": d})
    # Arrow-safe: cast UUID/object columns to string
    for c in list(df.columns):
        if df[c].dtype == "object" and df[c].astype(str).str.match(r"^[0-9a-fA-F-]{36}$").all():
            df[c] = df[c].astype(str)
    if "clutch_instance_id" in df.columns:
        df.rename(columns={"clutch_instance_id": "ci_id"}, inplace=True)
    return df

# UI
LOCAL_TODAY = pd.Timestamp.utcnow().tz_localize("UTC").date()
st.subheader("Pick a day")
day = st.date_input("Day", value=LOCAL_TODAY, key="overview_mounts_day")

df = _load_mounts_for_day(day)
if df.empty:
    st.warning("No mounts found for the selected day.", icon="⚠️")
else:
    st.dataframe(df, hide_index=True, width='stretch')
    st.caption(f"{len(df)} mount(s)")
