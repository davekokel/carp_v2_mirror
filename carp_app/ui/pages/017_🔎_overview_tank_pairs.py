# =============================================================================
# 🔎 Overview tank pairs — snapshot + latest CX codes & dates
#   - Shows v_tank_pairs rows
#   - Adds latest cross_code (CX) & clutch_code (CX) via lateral lookups
#   - Filters by code/fish/tank/genotype; date stays in columns
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from typing import Optional, List, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🔎 Overview tank pairs", page_icon="🔎", layout="wide")
st.title("🔎 Overview tank pairs")

# --- engine ---
if not os.getenv("DB_URL"):
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

VIEW = "public.v_tank_pairs"  # must include at least: id, tank_pair_code, mom/dad tank/fish/genotype, created_at

def _view_exists(schema: str, name: str) -> bool:
    with eng.begin() as cx:
        return pd.read_sql(
            text("""select 1
                    from information_schema.views
                    where table_schema=:s and table_name=:t
                    limit 1"""),
            cx, params={"s": schema, "t": name}
        ).shape[0] > 0

if not _view_exists("public","v_tank_pairs"):
    st.error("Required view public.v_tank_pairs not found."); st.stop()

# --- filters ---
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([3,1,1,1])
    q  = c1.text_input("Search (pair code / fish / tank / genotype)")
    d1 = c2.date_input("Created from", value=None)
    d2 = c3.date_input("Created to", value=None)
    status_val = c4.selectbox("Status", ["(any)","selected","scheduled","retired","closed"], index=0)
    _ = st.form_submit_button("Apply")

where, params = [], {}
if q:
    ql = f"%{q.strip()}%"
    bag = [
        "coalesce(tp.tank_pair_code,'') ilike :q",
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

# --- query tank pairs + latest CX cross/clutch ---
sql = text(f"""
  with tp as (
    select *
    from {VIEW}
    {where_sql}
  )
  select
    tp.id,
    tp.tank_pair_code,
    tp.status,
    tp.role_orientation,
    tp.created_by,
    tp.created_at,

    tp.mom_fish_code, tp.mom_tank_code, tp.mom_genotype,
    tp.dad_fish_code, tp.dad_tank_code, tp.dad_genotype,

    -- pretty helpers, if present in the view we keep them; else derive
    case
      when tp.pair_fish   is not null then tp.pair_fish
      else coalesce(tp.mom_fish_code,'') || ' × ' || coalesce(tp.dad_fish_code,'')
    end as pair_fish,

    case
      when tp.pair_tanks  is not null then tp.pair_tanks
      else coalesce(tp.mom_tank_code,'') || ' × ' || coalesce(tp.dad_tank_code,'')
    end as pair_tanks,

    case
      when tp.genotype    is not null then tp.genotype
      else coalesce(
             nullif(tp.mom_genotype,'') || case when coalesce(tp.mom_genotype,'')<>'' and coalesce(tp.dad_genotype,'')<>'' then ' × ' else '' end || nullif(tp.dad_genotype,''),
             nullif(tp.mom_genotype,'')
           )
    end as genotype,

    -- latest cross (CX), if any
    cx.cross_code        as latest_cross_code,
    cx.cross_date        as latest_cross_date,

    -- latest clutch (CX), if any (same code), plus birth date
    cl.clutch_code       as latest_clutch_code,
    cl.birthday          as latest_birth_date

  from tp
  left join lateral (
    select ci.cross_code, ci.cross_date
    from public.cross_instances ci
    where ci.tank_pair_id = tp.id
    order by ci.created_at desc nulls last, ci.cross_date desc nulls last
    limit 1
  ) cx on true
  left join lateral (
    select cl.clutch_code, cl.birthday
    from public.clutch_instances cl
    join public.cross_instances ci on ci.id = cl.cross_instance_id
    where ci.tank_pair_id = tp.id
    order by cl.created_at desc nulls last, cl.birthday desc nulls last
    limit 1
  ) cl on true
  order by tp.created_at desc nulls last
  limit 500
""")

with eng.begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} pair(s)")
if df.empty:
    st.info("No tank pairs match your filters.")
    st.stop()

# friendlier default order
cols = [
    "tank_pair_code","status","created_at",
    "pair_fish","pair_tanks","genotype",
    "latest_cross_code","latest_cross_date",
    "latest_clutch_code","latest_birth_date",
    "created_by",
]
show = [c for c in cols if c in df.columns]
st.dataframe(df[show], width="stretch", hide_index=True)