from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()
from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Daily Overviews (All)", page_icon="📊", layout="wide")
st.title("📊 Daily Overviews — All Entities")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

# ---------- controls ----------
colA, colB = st.columns([1,1])
with colA:
    days = st.slider("Days to show", min_value=7, max_value=180, value=30, step=1)
with colB:
    st.caption("Showing newest → oldest in each table")

# ---------- helpers ----------
def _fetch(mv: str, day_col: str, n_days: int) -> pd.DataFrame:
    sql = text(f"select * from {mv} order by {day_col} desc limit :lim")
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params={"lim": int(n_days)})
    return df

def _kpi_band(df: pd.DataFrame, primary_col: str, day_col: str, secondary: tuple[str,str] | None = None):
    c1, c2, c3 = st.columns([1,1,1])
    total = int(df.get(primary_col, pd.Series([0])).fillna(0).sum()) if primary_col in df.columns else len(df)
    c1.metric(primary_col.replace("_", " ").title(), f"{total}")
    if secondary and secondary[1] in df.columns:
        label, col = secondary
        c2.metric(label, f"{int(df[col].fillna(0).sum())}")
    c3.metric("Days", f"{len(df)}")

st.divider()

# ---------- Mounts ----------
st.subheader("🧪 Mounts (daily)")
mounts_df = _fetch("public.mv_overview_mounts_daily", "mount_day", days)
if mounts_df.empty:
    st.caption("No data yet.")
else:
    _kpi_band(mounts_df, primary_col="mounts_count", day_col="mount_day",
              secondary=("Embryos total", "embryos_total_sum"))
    cols = ["mount_day","mounts_count","embryos_total_sum","runs_count","clutches_count","last_time_mounted","orientations_json"]
    st.dataframe(mounts_df[[c for c in cols if c in mounts_df.columns]],
                 hide_index=True, use_container_width=True)

st.divider()

# ---------- Crosses (runs) ----------
st.subheader("🧬 Crosses — Runs (daily)")
runs_df = _fetch("public.mv_overview_crosses_daily", "run_day", days)
if runs_df.empty:
    st.caption("No data yet.")
else:
    _kpi_band(runs_df, primary_col="runs_count", day_col="run_day")
    cols = ["run_day","runs_count","clutches_count","last_run_date"]
    st.dataframe(runs_df[[c for c in cols if c in runs_df.columns]],
                 hide_index=True, use_container_width=True)

st.divider()

# ---------- Clutches (annotations) ----------
st.subheader("🐣 Clutches — Annotations (daily)")
ann_df = _fetch("public.mv_overview_clutches_daily", "annot_day", days)
if ann_df.empty:
    st.caption("No data yet.")
else:
    _kpi_band(ann_df, primary_col="annotations_count", day_col="annot_day")
    cols = ["annot_day","annotations_count","last_annotated"]
    st.dataframe(ann_df[[c for c in cols if c in ann_df.columns]],
                 hide_index=True, use_container_width=True)

st.divider()

# ---------- Tanks ----------
st.subheader("🫙 Tanks (daily)")
tanks_df = _fetch("public.mv_overview_tanks_daily", "tank_day", days)
if tanks_df.empty:
    st.caption("No data yet.")
else:
    _kpi_band(tanks_df, primary_col="tanks_created", day_col="tank_day")
    cols = ["tank_day","tanks_created","active_count","activated_count","last_seen_at","last_created"]
    st.dataframe(tanks_df[[c for c in cols if c in tanks_df.columns]],
                 hide_index=True, use_container_width=True)

st.divider()

# ---------- Fish ----------
st.subheader("🐟 Fish (daily)")
fish_df = _fetch("public.mv_overview_fish_daily", "fish_day", days)
if fish_df.empty:
    st.caption("No data yet.")
else:
    _kpi_band(fish_df, primary_col="fish_created", day_col="fish_day",
              secondary=("Births logged", "births_logged"))
    cols = ["fish_day","fish_created","births_logged","last_created"]
    st.dataframe(fish_df[[c for c in cols if c in fish_df.columns]],
                 hide_index=True, use_container_width=True)

st.divider()

# ---------- Plasmids ----------
st.subheader("🧫 Plasmids (daily)")
plasm_df = _fetch("public.mv_overview_plasmids_daily", "plasmid_day", days)
if plasm_df.empty:
    st.caption("No data yet.")
else:
    _kpi_band(plasm_df, primary_col="plasmids_created", day_col="plasmid_day")
    cols = ["plasmid_day","plasmids_created","last_created"]
    st.dataframe(plasm_df[[c for c in cols if c in plasm_df.columns]],
                 hide_index=True, use_container_width=True)