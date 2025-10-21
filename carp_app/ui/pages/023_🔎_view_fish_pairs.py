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
from carp_app.lib.config import engine as get_engine

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
def _cached_engine(url: str):
    return get_engine()

def _get_engine():
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _cached_engine(url)

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

def _table_cols(schema: str, name: str) -> t.List[str]:
    with _get_engine().begin() as cx:
        df = pd.read_sql(text("""
          select column_name
          from information_schema.columns
          where table_schema=:s and table_name=:t
          order by ordinal_position
        """), cx, params={"s": schema, "t": name})
    return df["column_name"].tolist()

def _has_col(schema: str, name: str, col: str) -> bool:
    return col in _table_cols(schema, name)

# ─────────────────────────────────────────────────────────────────────────────
# Data loads
# ─────────────────────────────────────────────────────────────────────────────
def _load_fish_pairs_overview(d1: date, d2: date, q: str) -> pd.DataFrame:
    """
    Overview per fish_pair with:
      identity, backgrounds, cleaned rollups,
      counts (selected/scheduled tank_pairs), last activity,
      linked concept summary (count + last concept code & genotype).
    """
    ci_has_tp = _has_col("public", "cross_instances", "tank_pair_id")

    sql = f"""
      with fp as (
        select
          fp.id::uuid           as fish_pair_id,
          mf.fish_code          as mom_fish_code,
          df.fish_code          as dad_fish_code
        from public.fish_pairs fp
        join public.fish mf on mf.id = fp.mom_fish_id
        join public.fish df on df.id = fp.dad_fish_id
      ),
      mom_clean as (
        select
          fish_code,
          coalesce(genetic_background,'') as mom_background,
          coalesce(genotype,'')           as mom_rollup
        from public.v_fish
      ),
      dad_clean as (
        select
          fish_code,
          coalesce(genetic_background,'') as dad_background,
          coalesce(genotype,'')           as dad_rollup
        from public.v_fish
      ),
      tps as (
        select
          tp.fish_pair_id::uuid  as fish_pair_id,
          count(*) filter (where tp.status = 'selected')::int  as n_selected,
          count(*) filter (where tp.status = 'scheduled')::int as n_scheduled,
          max(tp.created_at)                                   as last_tank_pair_at
        from public.tank_pairs tp
        where tp.created_at::date between :d1 and :d2
        group by tp.fish_pair_id
      ),
      concept_counts as (
        select cp.mom_code, cp.dad_code, count(*)::int as n_concepts_total
        from public.clutch_plans cp
        group by cp.mom_code, cp.dad_code
      ),
      last_concept as (
        select
          cp.mom_code, cp.dad_code,
          cp.clutch_code       as last_concept_code,
          cp.planned_name      as concept_genotype,
          cp.planned_nickname  as last_planned_nickname,
          cp.created_at,
          row_number() over (partition by cp.mom_code, cp.dad_code order by cp.created_at desc) as rn
        from public.clutch_plans cp
      )
      {", ci as ( select t.fish_pair_id::uuid as fish_pair_id, max(ci.created_at) as last_cross_at from public.cross_instances ci join public.tank_pairs t on t.id = ci.tank_pair_id group by t.fish_pair_id )" if ci_has_tp else ""}
      select
        fp.fish_pair_id,
        fp.mom_fish_code, fp.dad_fish_code,

        coalesce(mc.mom_background,'') as mom_background,
        coalesce(dc.dad_background,'') as dad_background,
        coalesce(mc.mom_rollup,'')     as mom_rollup,
        coalesce(dc.dad_rollup,'')     as dad_rollup,

        coalesce(tps.n_selected,0)     as n_selected,
        coalesce(tps.n_scheduled,0)    as n_scheduled,
        tps.last_tank_pair_at,

        coalesce(cc.n_concepts_total,0)  as n_concepts_total,
        coalesce(lc.last_concept_code,'') as last_concept_code,
        coalesce(lc.concept_genotype,'')  as concept_genotype,
        coalesce(lc.last_planned_nickname,'') as last_planned_nickname,

        greatest(
          coalesce(tps.last_tank_pair_at, timestamp 'epoch')
          {", coalesce(ci.last_cross_at, timestamp 'epoch')" if ci_has_tp else ""}
        ) as last_activity_at

      from fp
      left join mom_clean mc on mc.fish_code = fp.mom_fish_code
      left join dad_clean dc on dc.fish_code = fp.dad_fish_code
      left join tps on tps.fish_pair_id = fp.fish_pair_id
      left join concept_counts cc
             on cc.mom_code = fp.mom_fish_code and cc.dad_code = fp.dad_fish_code
      left join last_concept lc
             on lc.mom_code = fp.mom_fish_code and lc.dad_code = fp.dad_fish_code and lc.rn = 1
      { "left join ci on ci.fish_pair_id = fp.fish_pair_id" if ci_has_tp else "" }
      where (:qq = '' or fp.mom_fish_code ilike :ql or fp.dad_fish_code ilike :ql)
      order by last_activity_at desc nulls last, fp.mom_fish_code, fp.dad_fish_code
      limit 1000
    """
    with _get_engine().begin() as cx:
        df = pd.read_sql(text(sql), cx, params={
            "d1": d1, "d2": d2,
            "qq": q or "", "ql": f"%{q or ''}%"
        })
    return df

def _load_tank_pairs_for_fish_pair(fish_pair_id: str, status: t.Optional[str] = None) -> pd.DataFrame:
    if _view_exists("public", "v_tank_pairs"):
        sql = f"""
          select v.*, tp.id::uuid as tank_pair_id
          from public.v_tank_pairs v
          join public.tank_pairs tp
            on tp.mother_tank_id = v.mother_tank_id
           and tp.father_tank_id = v.father_tank_id
          where tp.fish_pair_id = cast(:fp as uuid)
          { "and v.status = :st" if status else "" }
          order by coalesce(v.created_at, tp.created_at) desc nulls last
        """
        with _get_engine().begin() as cx:
            return pd.read_sql(text(sql), cx, params={"fp": fish_pair_id, **({"st": status} if status else {})})

    # Fallback: build from base tables if v_tank_pairs is missing
    with _get_engine().begin() as cx:
        return pd.read_sql(text(f"""
          select
            tp.id::uuid               as tank_pair_id,
            coalesce(tp.tank_pair_code,'') as tank_pair_code,
            tp.concept_id,
            coalesce(cp.clutch_code, cp.id::text) as clutch_code,
            tp.status,
            tp.created_by,
            tp.created_at,
            mf.fish_code              as mom_fish_code,
            vt_m.tank_code            as mom_tank_code,
            df.fish_code              as dad_fish_code,
            vt_f.tank_code            as dad_tank_code
          from public.tank_pairs tp
          join public.fish_pairs fp on fp.id = tp.fish_pair_id
          join public.fish mf on mf.id = fp.mom_fish_id
          join public.fish df on df.id = fp.dad_fish_id
          left join public.clutch_plans cp on cp.id = tp.concept_id
          left join public.v_tanks vt_m on vt_m.tank_id = tp.mother_tank_id
          left join public.v_tanks vt_f on vt_f.tank_id = tp.father_tank_id
          where tp.fish_pair_id = cast(:fp as uuid)
          { "and tp.status = :st" if status else "" }
          order by tp.created_at desc nulls last
        """), cx, params={"fp": fish_pair_id, **({"st": status} if status else {})})

def _load_cross_instances_for_fish_pair(fish_pair_id: str, d1: date, d2: date) -> pd.DataFrame:
    sql = """
      with pairs as (
        select id as tank_pair_id
        from public.tank_pairs
        where fish_pair_id = cast(:fp as uuid)
      )
      select
        coalesce(nullif(ci.cross_run_code,''), ci.id::text) as cross_run,
        ci.cross_date                                       as date,
        ci.created_by,
        tp.tank_pair_code                                   as cross_code
      from public.cross_instances ci
      join pairs p          on p.tank_pair_id = ci.tank_pair_id
      left join public.tank_pairs tp on tp.id = ci.tank_pair_id
      where ci.cross_date between :d1 and :d2
      order by ci.created_at desc
      limit 200
    """
    with _get_engine().begin() as cx:
        return pd.read_sql(text(sql), cx, params={"fp": fish_pair_id, "d1": d1, "d2": d2})
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

# Friendly pair label
fp["pair_label"] = fp["mom_fish_code"] + " × " + fp["dad_fish_code"]

# Display columns (no token scoring)
l1_cols = [
    "mom_fish_code","dad_fish_code","pair_label",
    "mom_background","dad_background",
    "mom_rollup","dad_rollup",
    "concept_genotype","last_concept_code","last_planned_nickname",
    "n_concepts_total","n_selected","n_scheduled",
    "last_tank_pair_at","last_activity_at",
]
for c in l1_cols:
    if c not in fp.columns:
        fp[c] = ""  # safe default

grid = fp[l1_cols].copy()
grid.insert(0, "✓ Open", False)

edit = st.data_editor(
    grid, hide_index=True, use_container_width=True, num_rows="fixed",
    column_config={
        "✓ Open":                st.column_config.CheckboxColumn("✓", default=False),
        "mom_fish_code":         st.column_config.TextColumn("mom_fish_code", disabled=True),
        "dad_fish_code":         st.column_config.TextColumn("dad_fish_code", disabled=True),
        "pair_label":            st.column_config.TextColumn("pair", disabled=True),
        "mom_background":        st.column_config.TextColumn("mom_bg", disabled=True),
        "dad_background":        st.column_config.TextColumn("dad_bg", disabled=True),
        "mom_rollup":            st.column_config.TextColumn("mom_rollup", disabled=True, width="large"),
        "dad_rollup":            st.column_config.TextColumn("dad_rollup", disabled=True, width="large"),
        "concept_genotype":      st.column_config.TextColumn("concept_genotype", disabled=True, width="large"),
        "last_concept_code":     st.column_config.TextColumn("last_concept_code", disabled=True),
        "last_planned_nickname": st.column_config.TextColumn("last_planned_nickname", disabled=True),
        "n_concepts_total":      st.column_config.NumberColumn("#concepts", disabled=True),
        "n_selected":            st.column_config.NumberColumn("#selected", disabled=True),
        "n_scheduled":           st.column_config.NumberColumn("#scheduled", disabled=True),
        "last_tank_pair_at":     st.column_config.DatetimeColumn("last_tank_pair_at", disabled=True),
        "last_activity_at":      st.column_config.DatetimeColumn("last_activity_at", disabled=True),
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
        # find the row in fp that matches this tab
        match = fp[(fp["mom_fish_code"]==r.mom_fish_code) & (fp["dad_fish_code"]==r.dad_fish_code)]
        fish_pair_id = str(match["fish_pair_id"].iloc[0]) if not match.empty else ""

        # fetch tank_pairs
        tps = _load_tank_pairs_for_fish_pair(fish_pair_id, selected_status)
        if tps.empty:
            st.info("No tank_pairs match the filter.")
        else:
            disp_cols = ["tank_pair_code","clutch_code","status",
                        "mom_fish_code","mom_tank_code","dad_fish_code","dad_tank_code",
                        "created_by","created_at"]
            disp_cols = [c for c in disp_cols if c in tps.columns]
            if "tank_pair_id" in tps.columns and "tank_pair_id" not in disp_cols:
              disp_cols.append("tank_pair_id")
            st.dataframe(tps[disp_cols], use_container_width=True, hide_index=True)

        # recent instances
        st.caption("Recent scheduled cross instances")
        ci = _load_cross_instances_for_fish_pair(fish_pair_id, start, end)
        if ci.empty:
            st.info("No recent cross instances for this fish pair.")
        else:
            ci2 = ci.rename(columns={"date":"cross_date"})
            ci_cols = ["cross_run","cross_date","created_by","cross_code"]
            st.dataframe(ci2[ci_cols], use_container_width=True, hide_index=True)

st.caption("Tip: use **select parent tanks** to create new tank_pairs (status=selected), then promote them on **schedule new cross**.")