from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from pathlib import Path
from typing import List, Tuple, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth

sb, session, user = require_auth()
from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Overview — Crosses", page_icon="🔎", layout="wide")
st.title("🔎 Overview tank pairs")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

VIEW_SCHEMA = "public"
VIEW_NAME   = "v_crosses"
RUNS_VIEW   = "v_cross_runs"

def _status_badge(s: str) -> str:
    s = (s or "").lower().strip()
    return {
        "draft": "🟣 draft",
        "ready": "🟢 ready",
        "scheduled": "🔵 scheduled",
        "closed": "⚫ closed",
    }.get(s, s or "")

def _view_exists(schema: str, name: str) -> bool:
    with eng.begin() as cx:
        return pd.read_sql(
            text("""select 1 from information_schema.views
                     where table_schema=:s and table_name=:t limit 1"""),
            cx, params={"s": schema, "t": name}
        ).shape[0] > 0

if not _view_exists(VIEW_SCHEMA, VIEW_NAME):
    st.error(f"Required view {VIEW_SCHEMA}.{VIEW_NAME} not found."); st.stop()

with eng.begin() as cx:
    cols = pd.read_sql(
        text("""select column_name
                from information_schema.columns
                where table_schema=:s and table_name=:t
                order by ordinal_position"""),
        cx, params={"s": VIEW_SCHEMA, "t": VIEW_NAME}
    )["column_name"].tolist()
have = {c.lower(): c for c in cols}

def pick(*opts: str, default: Optional[str] = None) -> Optional[str]:
    for c in opts:
        if c.lower() in have:
            return have[c.lower()]
    return default

col_id        = pick("cross_id","id")
col_code      = pick("cross_code","code")
col_status    = pick("status")
col_created   = pick("created_at","created_time","created_ts")
col_latest    = pick("latest_cross_date")

with st.form("filters"):
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    q  = c1.text_input("Search (code/mom/dad)")
    d1 = c2.date_input("Created from", value=None)
    d2 = c3.date_input("Created to", value=None)
    status_filter = c4.selectbox("Status", ["(any)","draft","ready","scheduled","closed"], index=0)
    _ = st.form_submit_button("Apply")

where_parts, params = [], {}
if q:
    q_like = f"%{q.strip()}%"
    sub = []
    for cand in ["cross_code","mom_code","dad_code","created_by"]:
        c = pick(cand)
        if c: sub.append(f"coalesce(c.{c}::text,'') ilike :q")
    if sub:
        where_parts.append("(" + " OR ".join(sub) + ")")
        params["q"] = q_like

if d1 and col_created:
    where_parts.append(f"c.{col_created} >= :d1"); params["d1"] = str(d1)
if d2 and col_created:
    where_parts.append(f"c.{col_created} <= :d2"); params["d2"] = str(d2)
if status_filter != "(any)" and col_status:
    where_parts.append(f"coalesce(c.{col_status},'draft') = :st"); params["st"] = status_filter

where_sql = (" where " + " AND ".join(where_parts)) if where_parts else ""
created_ord = col_created if col_created else (cols[0] if cols else "created_at")

sql = text(f"""
  select c.*
  from {VIEW_SCHEMA}.{VIEW_NAME} c
  {where_sql}
  order by c.{created_ord} desc nulls last
  limit 500
""")
with eng.begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"Rows from {VIEW_SCHEMA}.{VIEW_NAME}")
st.caption(f"{len(df)} cross(es)")
if df.empty:
    st.info("No crosses match."); st.stop()

sel_key = next((c for c in [col_code, col_id] if c and c in df.columns), None) or df.columns[0]

key = "_crosses_overview_table"
def _new_session_table() -> pd.DataFrame:
    t = df.copy()
    vis = [*t.columns]
    if sel_key not in vis:
        vis.insert(0, sel_key)
        t = t[vis]
    t.insert(0, "✓ Select", False)
    if col_status and (col_status in t.columns):
        t.insert(1, "status_badge", t[col_status].map(_status_badge))
    else:
        t.insert(1, "status_badge", "")
    return t

if key not in st.session_state:
    st.session_state[key] = _new_session_table()
else:
    base = st.session_state[key].set_index(sel_key, drop=False)
    now = df.copy().set_index(sel_key, drop=False)
    if col_status and (col_status in now.columns):
        now.insert(0, "status_badge", now[col_status].map(_status_badge))
    else:
        now.insert(0, "status_badge", "")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
        else:
            for c in now.columns:
                if c not in ("✓ Select",):
                    base.at[i, c] = now.at[i, c]
    base = base.loc[now.index]
    st.session_state[key] = base.reset_index(drop=True)

visible = ["✓ Select"]
data_cols = [c for c in st.session_state[key].columns if c not in ("✓ Select", "id")]
if sel_key not in data_cols:
    data_cols.insert(0, sel_key)
visible += data_cols

edited = st.data_editor(
    st.session_state[key][visible],
    hide_index=True,
    use_container_width=True,
    column_order=visible,
    column_config={
        "✓ Select":     st.column_config.CheckboxColumn("✓", default=False),
        "status_badge": st.column_config.TextColumn("status_badge", disabled=True),
    },
    key="crosses_editor",
)
if "✓ Select" in edited.columns:
    st.session_state[key].loc[edited.index, "✓ Select"] = edited["✓ Select"]

mask = edited.get("✓ Select", pd.Series(False, index=edited.index)).fillna(False).astype(bool)
sel_keys = edited.loc[mask, sel_key].astype(str).tolist()
if not sel_keys:
    st.info("Select one or more crosses to show runs."); st.stop()

st.divider()
st.subheader("Runs for selected crosses")

def _fetch_runs_for_cross(row: pd.Series) -> Tuple[pd.DataFrame, Optional[str]]:
    with eng.begin() as cx:
        if col_id and (col_id in row.index) and pd.notna(row[col_id]):
            runs = pd.read_sql(
                text(f"""
                  select *
                  from {VIEW_SCHEMA}.{RUNS_VIEW}
                  where cross_id = cast(:cid as uuid)
                  order by run_created_at desc nulls last, cross_date desc nulls last
                  limit 1000
                """),
                cx, params={"cid": row[col_id]}
            )
        elif col_code and (col_code in row.index) and str(row[col_code]).strip():
            runs = pd.read_sql(
                text(f"""
                  select *
                  from {VIEW_SCHEMA}.{RUNS_VIEW}
                  where cross_code = :code
                  order by run_created_at desc nulls last, cross_date desc nulls last
                  limit 1000
                """),
                cx, params={"code": str(row[col_code])}
            )
        else:
            return pd.DataFrame(), "Cannot resolve cross: no usable id/code."
        if runs.empty:
            return pd.DataFrame(), "No runs yet for this cross."
        return runs, None

any_found = False
for _, row in edited[edited["✓ Select"] == True].iterrows():
    row_key_val = str(row[sel_key])
    st.markdown(f"**{row_key_val}**")
    try:
        runs, warn = _fetch_runs_for_cross(row)
    except Exception as e:
        st.warning(f"Failed for {row_key_val}: {e}")
        st.markdown("---")
        continue

    if warn:
        st.info(warn); st.markdown("---"); continue
    if runs.empty:
        st.caption("No runs."); st.markdown("---"); continue

    any_found = True
    show = [
        "cross_run_code","cross_date",
        "mom_code","dad_code",
        "mother_tank_label","father_tank_label",
        "run_created_by","run_created_at","run_note"
    ]
    st.dataframe(runs[[c for c in show if c in runs.columns]], use_container_width=True, hide_index=True)
    st.markdown("---")

if not any_found:
    st.info("No run rows found for selected cross(es).")