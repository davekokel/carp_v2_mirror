from __future__ import annotations
from carp_app.lib.time import utc_today

# ── sys.path prime ───────────────────────────────────────────────────────────
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── auth gates ───────────────────────────────────────────────────────────────
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# ── std/3p ───────────────────────────────────────────────────────────────────
import os
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── app libs ─────────────────────────────────────────────────────────────────
from carp_app.lib.db import get_engine as _create_engine

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="CARP — 🔎 Overview Mounts", page_icon="🔎", layout="wide")
st.title("🔎 Overview Mounts")

# ── engine cache ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _eng() -> Engine:
    return _cached_engine()

# ── helpers ─────────────────────────────────────────────────────────────────
def _view_exists(schema: str, name: str) -> bool:
    q = text("""
      select 1
      from information_schema.views
      where table_schema=:s and table_name=:n
      limit 1
    """)
    with _eng().begin() as cx:
        return pd.read_sql(q, cx, params={"s": schema, "n": name}).shape[0] > 0

def _table_exists(schema: str, name: str) -> bool:
    q = text("""
      select 1
      from information_schema.tables
      where table_schema=:s and table_name=:n
      limit 1
    """)
    with _eng().begin() as cx:
        return pd.read_sql(q, cx, params={"s": schema, "n": name}).shape[0] > 0

def _columns(schema: str, name: str) -> list[str]:
    q = text("""
      select column_name
      from information_schema.columns
      where table_schema=:s and table_name=:n
      order by ordinal_position
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(q, cx, params={"s": schema, "n": name})
    return [c for c in df["column_name"].tolist()]

def _fetch_mounts(source_schema: str, source_name: str, day: pd.Timestamp | None) -> pd.DataFrame:
    cols = _columns(source_schema, source_name)
    # Try to find a sensible date/timestamp column to filter by
    date_candidates = ["mounted_at", "imaged_at", "created_at", "event_at", "date", "timestamp"]
    date_col = next((c for c in date_candidates if c in cols), None)

    base_ident = f'{source_schema}.{source_name}'
    if day is not None and date_col is not None:
        sql = text(f"""
          select *
          from {base_ident}
          where date({date_col}) = :d
          order by {date_col} desc nulls last
          limit 1000
        """)
        params = {"d": pd.Timestamp(day).date()}
    else:
        sql = text(f"""
          select *
          from {base_ident}
          order by 1
          limit 1000
        """)
        params = {}

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df

# ── filters ─────────────────────────────────────────────────────────────────
# UTC-safe "today" (works across pandas versions)
today = utc_today()
with st.form("filters"):
    c1, c2 = st.columns([1, 1])
    with c1:
        day = st.date_input("Day", value=today)
    with c2:
        source_pref = st.selectbox(
            "Data source preference",
            ["auto (try view, then table)", "view: public.v_overview_mounts", "table: public.bruker_mounts"],
            index=0
        )
    submitted = st.form_submit_button("Apply")

# ── source resolution ────────────────────────────────────────────────────────
src_schema, src_name, resolved = "public", None, None
if source_pref.startswith("view"):
    src_name = "v_overview_mounts"
    if _view_exists(src_schema, src_name):
        resolved = ("view", src_schema, src_name)
    else:
        st.warning("Requested view `public.v_overview_mounts` not found; falling back to auto.")
        src_name = None

if resolved is None and source_pref.startswith("table"):
    src_name = "bruker_mounts"
    if _table_exists(src_schema, src_name):
        resolved = ("table", src_schema, src_name)
    else:
        st.warning("Requested table `public.bruker_mounts` not found; falling back to auto.")
        src_name = None

if resolved is None:
    # auto: prefer a view if present, else the table
    if _view_exists("public", "v_overview_mounts"):
        resolved = ("view", "public", "v_overview_mounts")
    elif _table_exists("public", "bruker_mounts"):
        resolved = ("table", "public", "bruker_mounts")

if resolved is None:
    st.error("No mounts source found. Expected one of: `public.v_overview_mounts` (view) or `public.bruker_mounts` (table).")
    st.stop()

kind, s, n = resolved
st.caption(f"Source: **{kind}** `{s}.{n}`")

# ── data fetch & display ────────────────────────────────────────────────────
try:
    df = _fetch_mounts(s, n, day)
    if df.empty:
        st.info("No rows for the selected day (or source). Try another day or remove day filter.")
    else:
        # Light column prettifying if common columns exist
        rename_map = {
            "mounted_at": "Mounted at",
            "imaged_at": "Imaged at",
            "created_at": "Created at",
            "sample_id": "Sample ID",
            "mount_id": "Mount ID",
            "operator": "Operator",
            "instrument": "Instrument",
            "notes": "Notes",
        }
        view = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}).copy()
        st.dataframe(view, use_container_width=True)
        st.caption(f"{len(df)} row(s)")
except Exception as e:
    st.error(f"Query failed: {type(e).__name__}: {e}")
    with st.expander("Traceback / details"):
        st.code(str(e))
