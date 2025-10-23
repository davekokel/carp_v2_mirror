from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
import typing as t

import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine
from sqlalchemy.engine import Engine
# ─────────────────────────────────────────────────────────────────────────────
# Auth + Page
# ─────────────────────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🐟 Fish pairs → Tank pairs", page_icon="🐟", layout="wide")
st.title("🐟 Fish pairs → Tank pairs")

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# ─────────────────────────────────────────────────────────────────────────────
# DB engine (cache keyed by DB_URL) + caption
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    return get_engine()

def _get_engine():
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _cached_engine()

with _get_engine().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _view_exists(schema: str, name: str) -> bool:
    with _get_engine().begin() as cx:
        n = pd.read_sql(
            text("select 1 from information_schema.views where table_schema=:s and table_name=:t limit 1"),
            cx, params={"s": schema, "t": name}
        ).shape[0]
    return n > 0

# ─────────────────────────────────────────────────────────────────────────────
# Data loads — TANK-CENTRIC (no fish_pairs / clutch_plans)
# ─────────────────────────────────────────────────────────────────────────────
def _load_fish_pairs_overview(d1: date, d2: date, q: str) -> pd.DataFrame:
    """
    Tank-centric fish-pair overview (no fish_pairs / clutch_plans).
    For each (mom_fish_code, dad_fish_code), show:
      - mom/dad backgrounds & rollups (from v_fish),
      - counts of tank_pairs by status (selected/scheduled) in date window,
      - last tank-pair time,
      - last cross instance time via tank_pairs → cross_instances,
      - last_activity_at = greatest(last_tank_pair_at, last_cross_at).
    """
    sql = """
      with tp_base as (
        select
          tp.id,
          tp.status,
          tp.created_at,
          vtm.fish_code as mom_fish_code,
          vtf.fish_code as dad_fish_code
        from public.tank_pairs tp
        left join public.v_tanks vtm on vtm.tank_id = tp.mother_tank_id
        left join public.v_tanks vtf on vtf.tank_id = tp.father_tank_id
        where coalesce(vtm.fish_code,'') <> '' and coalesce(vtf.fish_code,'') <> ''
      ),
      fp_distinct as (
        select
          min(id::text) as pair_key,  -- 👈 cast UUID to text to allow min()
          mom_fish_code,
          dad_fish_code
        from tp_base
        group by mom_fish_code, dad_fish_code
      ),
      mom_clean as (
        select fish_code,
               coalesce(genetic_background,'') as mom_background,
               coalesce(genotype,'')           as mom_rollup
        from public.v_fish
      ),
      dad_clean as (
        select fish_code,
               coalesce(genetic_background,'') as dad_background,
               coalesce(genotype,'')           as dad_rollup
        from public.v_fish
      ),
      tps as (
        select
          tb.mom_fish_code,
          tb.dad_fish_code,
          count(*) filter (where tb.status = 'selected')::int  as n_selected,
          count(*) filter (where tb.status = 'scheduled')::int as n_scheduled,
          max(tb.created_at)                                   as last_tank_pair_at
        from tp_base tb
        where tb.created_at::date between :d1 and :d2
        group by tb.mom_fish_code, tb.dad_fish_code
      ),
      last_cross as (
        select
          tb.mom_fish_code,
          tb.dad_fish_code,
          max(ci.created_at) as last_cross_at
        from tp_base tb
        join public.cross_instances ci on ci.tank_pair_id = tb.id
        group by tb.mom_fish_code, tb.dad_fish_code
      )
      select
        fp.pair_key,
        fp.mom_fish_code, fp.dad_fish_code,

        coalesce(mc.mom_background,'') as mom_background,
        coalesce(dc.dad_background,'') as dad_background,
        coalesce(mc.mom_rollup,'')     as mom_rollup,
        coalesce(dc.dad_rollup,'')     as dad_rollup,

        coalesce(tps.n_selected,0)     as n_selected,
        coalesce(tps.n_scheduled,0)    as n_scheduled,
        tps.last_tank_pair_at,
        lc.last_cross_at,
        greatest(
          coalesce(tps.last_tank_pair_at, timestamp 'epoch'),
          coalesce(lc.last_cross_at,     timestamp 'epoch')
        ) as last_activity_at

      from fp_distinct fp
      left join mom_clean mc on mc.fish_code = fp.mom_fish_code
      left join dad_clean dc on dc.fish_code = fp.dad_fish_code
      left join tps on tps.mom_fish_code = fp.mom_fish_code and tps.dad_fish_code = fp.dad_fish_code
      left join last_cross lc on lc.mom_fish_code = fp.mom_fish_code and lc.dad_fish_code = fp.dad_fish_code
      where (:qq = '' or fp.mom_fish_code ilike :ql or fp.dad_fish_code ilike :ql)
      order by last_activity_at desc nulls last, fp.mom_fish_code, fp.dad_fish_code
      limit 1000
    """
    with _get_engine().begin() as cx:
        df = pd.read_sql(
            text(sql), cx,
            params={"d1": d1, "d2": d2, "qq": q or "", "ql": f"%{q or ''}%"}
        )
    return df

def _load_tank_pairs_for_codes(mom_code: str, dad_code: str, status: t.Optional[str] = None) -> pd.DataFrame:
    sql = """
      select
        tp.id::uuid               as tank_pair_id,
        coalesce(tp.tank_pair_code,'') as tank_pair_code,
        tp.status,
        tp.created_by,
        tp.created_at,
        vtm.fish_code as mom_fish_code,
        vtm.tank_code as mom_tank_code,
        vtf.fish_code as dad_fish_code,
        vtf.tank_code as dad_tank_code
      from public.tank_pairs tp
      left join public.v_tanks vtm on vtm.tank_id = tp.mother_tank_id
      left join public.v_tanks vtf on vtf.tank_id = tp.father_tank_id
      where vtm.fish_code = :m and vtf.fish_code = :d
      {status_clause}
      order by tp.created_at desc nulls last
    """.format(status_clause=("and tp.status = :st" if status else ""))
    params = {"m": mom_code, "d": dad_code}
    if status: params["st"] = status
    with _get_engine().begin() as cx:
        return pd.read_sql(text(sql), cx, params=params)

def _load_cross_instances_for_codes(mom_code: str, dad_code: str, d1: date, d2: date) -> pd.DataFrame:
    sql = """
      with tp as (
        select id
        from public.tank_pairs t
        left join public.v_tanks vtm on vtm.tank_id = t.mother_tank_id
        left join public.v_tanks vtf on vtf.tank_id = t.father_tank_id
        where vtm.fish_code = :m and vtf.fish_code = :d
      )
      select
        coalesce(nullif(ci.cross_run_code,''), ci.id::text) as cross_run,
        ci.cross_date                                       as date,
        ci.created_by,
        t.tank_pair_code                                    as cross_code
      from public.cross_instances ci
      join tp on tp.id = ci.tank_pair_id
      left join public.tank_pairs t on t.id = ci.tank_pair_id
      where ci.cross_date between :d1 and :d2
      order by ci.created_at desc
      limit 200
    """
    with _get_engine().begin() as cx:
        return pd.read_sql(text(sql), cx, params={"m": mom_code, "d": dad_code, "d1": d1, "d2": d2})

# ─────────────────────────────────────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3 = st.columns([1,1,2])
    with c1: start = st.date_input("From", value=today - timedelta(days=30))
    with c2: end   = st.date_input("To", value=today)
    with c3: q     = st.text_input("Search fish (mom/dad code contains)", value="")
    st.form_submit_button("Apply", use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# Level 1: Fish pairs (rich columns)
# ─────────────────────────────────────────────────────────────────────────────
st.header("Level 1 — Fish pairs")

fp = _load_fish_pairs_overview(start, end, q)
if fp.empty:
    st.info("No fish pairs found for the filters.")
    st.stop()

fp["pair_label"] = fp["mom_fish_code"] + " × " + fp["dad_fish_code"]

l1_cols = [
    "mom_fish_code","dad_fish_code","pair_label",
    "mom_background","dad_background",
    "mom_rollup","dad_rollup",
    "n_selected","n_scheduled",
    "last_tank_pair_at","last_cross_at","last_activity_at",
]
grid = fp[l1_cols].copy()
grid.insert(0, "✓ Open", False)

edit = st.data_editor(
    grid, hide_index=True, use_container_width=True,
    column_config={
        "✓ Open": st.column_config.CheckboxColumn("✓", default=False),
        "mom_fish_code": st.column_config.TextColumn("mom_fish_code", disabled=True),
        "dad_fish_code": st.column_config.TextColumn("dad_fish_code", disabled=True),
        "pair_label": st.column_config.TextColumn("pair", disabled=True),
        "mom_background": st.column_config.TextColumn("mom_bg", disabled=True),
        "dad_background": st.column_config.TextColumn("dad_bg", disabled=True),
        "mom_rollup": st.column_config.TextColumn("mom_rollup", disabled=True, width="large"),
        "dad_rollup": st.column_config.TextColumn("dad_rollup", disabled=True, width="large"),
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
    st.info("Select one or more fish pairs to drill down.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Level 2: Tank pairs (for selected fish pair)
# ─────────────────────────────────────────────────────────────────────────────
st.header("Level 2 — Tank pairs for selected fish pair(s)")

status_filter = st.selectbox("Status filter", options=["(all)","selected","scheduled"], index=0)
selected_status = None if status_filter == "(all)" else status_filter

tabs = st.tabs([f"{r.mom_fish_code} × {r.dad_fish_code}" for r in opened.itertuples(index=False)])

for tab, r in zip(tabs, opened.itertuples(index=False)):
    with tab:
        mom_code = r.mom_fish_code
        dad_code = r.dad_fish_code

        tps = _load_tank_pairs_for_codes(mom_code, dad_code, selected_status)
        if tps.empty:
            st.info("No tank_pairs match the filter.")
        else:
            disp_cols = ["tank_pair_code","status","mom_fish_code","mom_tank_code","dad_fish_code","dad_tank_code","created_by","created_at"]
            if "tank_pair_id" not in disp_cols:
                disp_cols.append("tank_pair_id")
            st.dataframe(tps[disp_cols], use_container_width=True, hide_index=True)

        st.caption("Recent scheduled cross instances")
        ci = _load_cross_instances_for_codes(mom_code, dad_code, start, end)
        if ci.empty:
            st.info("No recent cross instances for this fish pair.")
        else:
            ci2 = ci.rename(columns={"date":"cross_date"})
            st.dataframe(ci2[["cross_run","cross_date","created_by","cross_code"]], use_container_width=True, hide_index=True)

st.caption("Tip: use **select parent tanks** to create new tank_pairs (status=selected), then promote them on **schedule new cross**.")