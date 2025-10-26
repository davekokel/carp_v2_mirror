# =============================================================================
# 🔎 Overview tank pairs — snapshot + latest CX codes & dates
#   - Source: public.v_tank_pairs (now includes mom/dad genotypes)
#   - Latest cross/clutch via cross_instances.tank_pair_code
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

# ── Auth + page ──────────────────────────────────────────────────────────────
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

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([3,1,1,1])
    q  = c1.text_input("Search (pair code / fish / tank / genotype)")
    d1 = c2.date_input("Created from", value=None)
    d2 = c3.date_input("Created to", value=None)
    status_val = c4.selectbox("Status", ["(any)","selected","scheduled","retired","closed"], index=0)
    st.form_submit_button("Apply", use_container_width=True)

where, params = [], {}
if q:
    ql = f"%{q.strip()}%"
    bag = [
        "coalesce(tp.tank_pair_code,'') ilike :q",
        "coalesce(tp.fish_pair_code,'') ilike :q",
        "coalesce(tp.mom_fish_code,'') ilike :q",
        "coalesce(tp.dad_fish_code,'') ilike :q",
        "coalesce(tp.mom_tank_code,'') ilike :q",
        "coalesce(tp.dad_tank_code,'') ilike :q",
        "coalesce(tp.mom_genotype,'') ilike :q",
        "coalesce(tp.dad_genotype,'') ilike :q",
    ]
    where.append("(" + " OR ".join(bag) + ")")
    params["q"] = ql
if d1:
    where.append("tp.created_at >= :d1"); params["d1"] = str(d1)
if d2:
    where.append("tp.created_at <= :d2"); params["d2"] = str(d2)
if status_val != "(any)":
    where.append("coalesce(tp.status,'') = :st"); params["st"] = status_val

where_sql = (" where " + " AND ".join(where)) if where else ""

# ── Query ────────────────────────────────────────────────────────────────────
sql = text(f"""
  with tp as (
    select *
    from {VIEW}
    {where_sql}
  )
  select
    tp.id,
    tp.tank_pair_code,
    tp.fish_pair_code,
    tp.status,
    tp.created_by,
    tp.created_at,
    tp.mom_fish_code, tp.mom_tank_code, tp.mom_genotype,
    tp.dad_fish_code, tp.dad_tank_code, tp.dad_genotype,

    coalesce(tp.mom_fish_code,'') || ' × ' || coalesce(tp.dad_fish_code,'') as pair_fish,
    coalesce(tp.mom_tank_code,'') || ' × ' || coalesce(tp.dad_tank_code,'') as pair_tanks,

    cx.cross_code        as latest_cross_code,
    cx.cross_date        as latest_cross_date,
    cl.clutch_code       as latest_clutch_code,
    cl.clutch_created_at as latest_clutch_created_at

  from tp
  left join lateral (
    select ci.cross_run_code as cross_code, ci.cross_date
    from public.cross_instances ci
    where ci.tank_pair_code = tp.tank_pair_code
    order by ci.created_at desc nulls last, ci.cross_date desc nulls last
    limit 1
  ) cx on true
  left join lateral (
    select cl.clutch_instance_code as clutch_code,
           cl.created_at as clutch_created_at
    from public.clutch_instances cl
    join public.cross_instances ci on ci.id = cl.cross_instance_id
    where ci.tank_pair_code = tp.tank_pair_code
    order by cl.created_at desc nulls last
    limit 1
  ) cl on true
  order by tp.created_at desc nulls last
  limit 500
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} pair(s)")
if df.empty:
    st.info("No tank pairs match your filters."); st.stop()

cols = [
    "tank_pair_code","fish_pair_code","status","created_at",
    "pair_fish","pair_tanks",
    "mom_genotype","dad_genotype",
    "latest_cross_code","latest_cross_date",
    "latest_clutch_code","latest_clutch_created_at",
    "created_by",
]
show = [c for c in cols if c in df.columns]
st.dataframe(df[show], use_container_width=True, hide_index=True)