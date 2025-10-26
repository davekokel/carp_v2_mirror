# =============================================================================
# 🐟 Fish pairs → Tank pairs
#   - Level 1: conceptual fish pairs (from v_tank_pairs grouping)
#   - Level 2: concrete tank pairs for each fish pair (from v_tank_pairs)
#   - Cross lists via cross_instances.tank_pair_code
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
import typing as t

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

st.set_page_config(page_title="🐟 Fish pairs → Tank pairs", page_icon="🐟", layout="wide")
st.title("🐟 Fish pairs → Tank pairs")

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# ── Engine ───────────────────────────────────────────────────────────────────
if not os.getenv("DB_URL"):
    st.error("DB_URL not set"); st.stop()

@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    return get_engine()

with _eng().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

VIEW_TP = "public.v_tank_pairs"

# ── Data loads ───────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _vtp_cols() -> set[str]:
    with _eng().begin() as cx:
        df = pd.read_sql(text("""
            select column_name
            from information_schema.columns
            where table_schema='public' and table_name='v_tank_pairs'
        """), cx)
    return set(df["column_name"].tolist())

def _load_fish_pairs_overview(d1: date, d2: date, q: str) -> pd.DataFrame:
    cols = _vtp_cols()

    # base pairs (require fish_pair_code + mom/dad codes)
    base_where = "coalesce(mom_fish_code,'') <> '' and coalesce(dad_fish_code,'') <> ''"
    base_sql = f"""
      with base as (
        select
          fish_pair_code,
          least(mom_fish_code, dad_fish_code) as mom_code,
          greatest(mom_fish_code, dad_fish_code) as dad_code
        from public.v_tank_pairs
        where {base_where}
      ),
      pairs as (
        select distinct fish_pair_code, mom_code, dad_code from base
      )
    """

    # counts over v_tank_pairs
    have_status = "status" in cols
    have_created = "created_at" in cols
    have_tp_code = "tank_pair_code" in cols

    n_selected_expr  = "count(*) filter (where v.status='selected')::int"  if have_status else "0::int"
    n_scheduled_expr = "count(*) filter (where v.status='scheduled')::int" if have_status else "0::int"
    date_filter = "and v.created_at::date between :d1 and :d2" if have_created else ""
    last_tp_ts  = "max(v.created_at)" if have_created else "null::timestamp as"

    tps_sql = f"""
      , tps as (
        select
          v.fish_pair_code,
          {n_selected_expr}  as n_selected,
          {n_scheduled_expr} as n_scheduled,
          {last_tp_ts} last_tank_pair_at
        from public.v_tank_pairs v
        {'where 1=1 ' + date_filter if date_filter else ''}
        group by v.fish_pair_code
      )
    """

    # last cross time (only if we have tank_pair_code to join)
    last_cross_sql = f"""
      , last_cross as (
        select
          v.fish_pair_code,
          max(ci.created_at) as last_cross_at
        from public.v_tank_pairs v
        join public.cross_instances ci
          on {'v.tank_pair_code = ci.tank_pair_code' if have_tp_code else '1=0'}
        group by v.fish_pair_code
      )
    """

    # final select with search
    sql = text(base_sql + tps_sql + last_cross_sql + """
      select
        p.fish_pair_code,
        p.mom_code as mom_fish_code,
        p.dad_code as dad_fish_code,
        coalesce(tps.n_selected,0)  as n_selected,
        coalesce(tps.n_scheduled,0) as n_scheduled,
        tps.last_tank_pair_at,
        lc.last_cross_at,
        greatest(
          coalesce(tps.last_tank_pair_at, timestamp 'epoch'),
          coalesce(lc.last_cross_at,     timestamp 'epoch')
        ) as last_activity_at
      from pairs p
      left join tps       on tps.fish_pair_code = p.fish_pair_code
      left join last_cross lc on lc.fish_pair_code = p.fish_pair_code
      where (:qq = '' or p.fish_pair_code ilike :ql or p.mom_code ilike :ql or p.dad_code ilike :ql)
      order by last_activity_at desc nulls last, p.mom_code, p.dad_code
      limit 1000
    """)

    params = {
        "qq": q or "",
        "ql": f"%{q or ''}%"
    }
    if have_created:
        params["d1"] = d1
        params["d2"] = d2

    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params=params)

def _load_tank_pairs_for_fp(fp_code: str, status: t.Optional[str] = None) -> pd.DataFrame:
    sql = f"""
      select
        v.id::uuid                as tank_pair_id,
        v.tank_pair_code,
        v.fish_pair_code,
        v.status,
        v.created_by,
        v.created_at,
        v.mom_fish_code, v.mom_tank_code, v.mom_genotype,
        v.dad_fish_code, v.dad_tank_code, v.dad_genotype
      from {VIEW_TP} v
      where v.fish_pair_code = :fp
      {("and v.status = :st" if status else "")}
      order by v.created_at desc nulls last
    """
    params = {"fp": fp_code}
    if status: params["st"] = status
    with _eng().begin() as cx:
        return pd.read_sql(text(sql), cx, params=params)

def _load_cross_instances_for_fp(fp_code: str, d1: date, d2: date) -> pd.DataFrame:
    sql = text(f"""
      with tps as (
        select distinct tank_pair_code
        from {VIEW_TP}
        where fish_pair_code = :fp
      )
      select
        coalesce(nullif(ci.cross_run_code,''), ci.id::text) as cross_run,
        ci.cross_date,
        ci.created_by,
        ci.tank_pair_code
      from public.cross_instances ci
      join tps on tps.tank_pair_code = ci.tank_pair_code
      where ci.cross_date between :d1 and :d2
      order by ci.created_at desc
      limit 200
    """)
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params={"fp": fp_code, "d1": d1, "d2": d2})

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3 = st.columns([1,1,2])
    with c1: start = st.date_input("From", value=today - timedelta(days=30))
    with c2: end   = st.date_input("To", value=today)
    with c3: q     = st.text_input("Search (fish_pair_code or fish codes contains)", value="")
    st.form_submit_button("Apply", use_container_width=True)

# ── Level 1: Fish pairs ─────────────────────────────────────────────────────
st.header("Level 1 — Fish pairs")
fp = _load_fish_pairs_overview(start, end, q)
if fp.empty:
    st.info("No fish pairs found for the filters."); st.stop()

grid = fp.copy()
grid.insert(0, "✓ Open", False)
grid["pair_label"] = grid["mom_fish_code"] + " × " + grid["dad_fish_code"]

edit = st.data_editor(
    grid[[
        "✓ Open","fish_pair_code","pair_label",
        "n_selected","n_scheduled",
        "last_tank_pair_at","last_cross_at","last_activity_at",
    ]],
    hide_index=True,
    use_container_width=True,
    column_config={
        "✓ Open": st.column_config.CheckboxColumn("✓", default=False),
        "fish_pair_code": st.column_config.TextColumn("fish_pair_code", disabled=True),
        "pair_label": st.column_config.TextColumn("pair", disabled=True),
        "n_selected": st.column_config.NumberColumn("#selected", disabled=True),
        "n_scheduled": st.column_config.NumberColumn("#scheduled", disabled=True),
        "last_tank_pair_at": st.column_config.DatetimeColumn("last_tank_pair_at", disabled=True),
        "last_cross_at": st.column_config.DatetimeColumn("last_cross_at", disabled=True),
        "last_activity_at": st.column_config.DatetimeColumn("last_activity_at", disabled=True),
    },
    key="fish_pairs_editor",
)

mask_open = edit.get("✓ Open", pd.Series(False, index=edit.index)).fillna(False).astype(bool)
opened = edit[mask_open].reset_index(drop=True)
if opened.empty:
    st.info("Select one or more fish pairs to drill down."); st.stop()

# ── Level 2: Tank pairs for selected fish pairs ─────────────────────────────
st.header("Level 2 — Tank pairs for selected fish pair(s)")

status_filter = st.selectbox("Status filter", options=["(all)","selected","scheduled","retired","closed"], index=0)
selected_status = None if status_filter == "(all)" else status_filter

tabs = st.tabs([f"{r.fish_pair_code}" for r in opened.itertuples(index=False)])

for tab, r in zip(tabs, opened.itertuples(index=False)):
    with tab:
        fp_code = r.fish_pair_code

        tps = _load_tank_pairs_for_fp(fp_code, selected_status)
        if tps.empty:
            st.info("No tank_pairs match the filter.")
        else:
            disp = tps[[
                "tank_pair_code","fish_pair_code","status","created_by","created_at",
                "mom_fish_code","mom_tank_code","mom_genotype",
                "dad_fish_code","dad_tank_code","dad_genotype",
            ]]
            st.dataframe(disp, use_container_width=True, hide_index=True)

        st.caption("Recent scheduled cross instances")
        ci = _load_cross_instances_for_fp(fp_code, start, end)
        if ci.empty:
            st.info("No recent cross instances for this fish pair.")
        else:
            st.dataframe(ci[["cross_run","cross_date","created_by","tank_pair_code"]], use_container_width=True, hide_index=True)

st.caption("Tank pairs are keyed by tank_pair_code (TP), grouped under fish_pair_code (FP). Crosses reference TP via cross_instances.tank_pair_code.")