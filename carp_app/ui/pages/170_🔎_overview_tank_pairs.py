# carp_app/ui/pages/170_🔎_overview_tank_pairs.py
from __future__ import annotations
import sys, pathlib, os
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from datetime import date
from typing import Set
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
st.set_page_config(page_title="🔎 Overview tank pairs", page_icon="🔎", layout="wide")
st.title("🔎 Overview tank pairs")

# ── Engine ───────────────────────────────────────────────────────────────────
if not os.getenv("DB_URL"):
    st.error("DB_URL not set"); st.stop()

@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    return get_engine()

with _eng().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

VIEW = "public.v_tank_pairs"

# ── Schema checks ────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _view_cols() -> Set[str]:
    with _eng().begin() as cx:
        df = pd.read_sql(text("""
            select column_name
            from information_schema.columns
            where table_schema='public' and table_name='v_tank_pairs'
        """), cx)
    return set(df["column_name"].tolist())

@st.cache_data(show_spinner=False)
def _table_exists(s: str, t: str) -> bool:
    with _eng().begin() as cx:
        n = pd.read_sql(text("""
            select count(*)::int as n
            from information_schema.tables
            where table_schema=:s and table_name=:t
        """), cx, params={"s": s, "t": t})["n"][0]
    return n > 0

C = _view_cols()
have = lambda c: c in C
have_crosses = _table_exists("public", "crosses")
have_clutches = _table_exists("public", "clutch_instances")

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([3,1,1,1])
    q  = c1.text_input("Search (pair/fish/tank/genotype)")
    d1 = c2.date_input("Created from", value=None) if have("created_at") else None
    d2 = c3.date_input("Created to",   value=None) if have("created_at") else None
    status_val = c4.selectbox("Status", ["(any)","selected","scheduled","retired","closed"], index=0) if have("status") else "(any)"
    st.form_submit_button("Apply")

where, params = [], {}

if q:
    ql = f"%{q.strip()}%"
    bag = []
    if have("tank_pair_code"):  bag.append("coalesce(tp.tank_pair_code,'') ilike :q")
    if have("fish_pair_code"):  bag.append("coalesce(tp.fish_pair_code,'') ilike :q")
    if have("mom_fish_code"):   bag.append("coalesce(tp.mom_fish_code,'') ilike :q")
    if have("dad_fish_code"):   bag.append("coalesce(tp.dad_fish_code,'') ilike :q")
    if have("mom_tank_code"):   bag.append("coalesce(tp.mom_tank_code,'') ilike :q")
    if have("dad_tank_code"):   bag.append("coalesce(tp.dad_tank_code,'') ilike :q")
    if have("mom_genotype"):    bag.append("coalesce(tp.mom_genotype,'') ilike :q")
    if have("dad_genotype"):    bag.append("coalesce(tp.dad_genotype,'') ilike :q")
    if bag:
        where.append("(" + " OR ".join(bag) + ")")
        params["q"] = ql

if have("created_at") and d1:
    where.append("tp.created_at >= :d1"); params["d1"] = str(d1)
if have("created_at") and d2:
    where.append("tp.created_at <= :d2"); params["d2"] = str(d2)

if have("status") and status_val != "(any)":
    where.append("coalesce(tp.status,'') = :st"); params["st"] = status_val

where_sql = (" where " + " AND ".join(where)) if where else ""

# ── Adaptive SELECT pieces ───────────────────────────────────────────────────
sel = []
def add(col, alias=None, default_sql="null"):
    if have(col):
        sel.append(f"tp.{col}" + (f" as {alias}" if alias else ""))
    else:
        sel.append(f"{default_sql}" + (f" as {alias or col}"))

add("tank_pair_code")
add("fish_pair_code")
add("status", default_sql="'unknown'")
add("created_by")
add("created_at")
add("mom_fish_code")
add("mom_tank_code")
add("mom_genotype")
add("dad_fish_code")
add("dad_tank_code")
add("dad_genotype")

pair_fish_expr  = "coalesce(tp.mom_fish_code,'') || ' × ' || coalesce(tp.dad_fish_code,'')" if have("mom_fish_code") and have("dad_fish_code") else "null"
pair_tanks_expr = "coalesce(tp.mom_tank_code,'') || ' × ' || coalesce(tp.dad_tank_code,'')" if have("mom_tank_code") and have("dad_tank_code") else "null"

have_tp_code = have("tank_pair_code")
cx_join = "cr.tank_pair_code = tp.tank_pair_code" if have_tp_code else "1=0"

# lateral blocks depend on table existence (no guessing)
if have_crosses:
    lateral_cross = f"""
      left join lateral (
        select cr.cross_run_code as cross_code, cr.cross_date
        from public.crosses cr
        where {cx_join}
        order by cr.created_at desc nulls last, cr.cross_date desc nulls last
        limit 1
      ) cx on true
    """
else:
    lateral_cross = "left join lateral (select null::text as cross_code, null::date as cross_date) cx on true"

if have_crosses and have_clutches:
    lateral_clutch = f"""
      left join lateral (
        select cl.clutch_instance_code as clutch_code,
               cl.created_at as clutch_created_at
        from public.clutch_instances cl
        join public.crosses cr on cr.id = cl.cross_instance_id
        where {cx_join}
        order by cl.created_at desc nulls last
        limit 1
      ) cl on true
    """
else:
    lateral_clutch = "left join lateral (select null::text as clutch_code, null::timestamptz as clutch_created_at) cl on true"

order_clause = "tp.created_at desc nulls last, tp.tank_pair_code" if have("created_at") and have("tank_pair_code") else \
               "tp.created_at desc nulls last" if have("created_at") else \
               "tp.tank_pair_code" if have("tank_pair_code") else "1"

sql = text(f"""
  with tp as (
    select * from {VIEW}
    {where_sql}
  )
  select
    {", ".join(sel)},
    {pair_fish_expr}  as pair_fish,
    {pair_tanks_expr} as pair_tanks,
    cx.cross_code        as latest_cross_code,
    cx.cross_date        as latest_cross_date,
    cl.clutch_code       as latest_clutch_code,
    cl.clutch_created_at as latest_clutch_created_at
  from tp
  {lateral_cross}
  {lateral_clutch}
  order by {order_clause}
  limit 500
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} pair(s)")
if df.empty:
    st.info("No tank pairs match your filters."); st.stop()

cols = [
    "tank_pair_code","fish_pair_code","status","created_at","created_by",
    "pair_fish","pair_tanks",
    "mom_genotype","dad_genotype",
    "latest_cross_code","latest_cross_date",
    "latest_clutch_code","latest_clutch_created_at",
]
show = [c for c in cols if c in df.columns]
st.dataframe(df[show], width="stretch", hide_index=True)