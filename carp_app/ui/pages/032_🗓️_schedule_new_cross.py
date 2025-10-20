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

sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🗓️ Schedule new cross", page_icon="🗓️", layout="wide")
st.title("🗓️ Schedule new cross")

_msg = st.session_state.get("schedule_result")
if _msg:
    if _msg.get("made"):
        st.success(f"Scheduled {len(_msg['made'])} instance(s): {', '.join(_msg['made'])}")
    if _msg.get("dupes"):
        st.warning("Some selections were already scheduled for that date:\n- " + "\n- ".join(_msg["dupes"]))

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

@st.cache_resource(show_spinner=False)
def _cached_engine(url: str):
    return get_engine()

def _get_engine():
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _cached_engine(url)

def _db_banner():
    try:
        with _get_engine().begin() as cx:
            dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
            cnt = pd.read_sql(text("select count(*) n from public.v_clutches_overview_final"), cx)
        st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]} • {int(cnt['n'][0])} clutch row(s)")
    except Exception:
        pass

_db_banner()

LIVE_STATUSES = ("active","new_tank")
TANK_TYPES    = ("inventory_tank","holding_tank","nursery_tank")

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

def _load_clutch_concepts(d1: date, d2: date, created_by: str, q: str) -> pd.DataFrame:
    sql = text("""
    with mom_live as (
      select f.fish_code, count(*)::int as n_live
      from public.fish f
      join public.fish_tank_memberships m on m.fish_id=f.id and m.left_at is null
      join public.v_tanks_for_fish vt on vt.tank_id = m.container_id
      where c.status = any(:live_statuses) and c.container_type = any(:tank_types)
      group by f.fish_code
    ),
    dad_live as (
      select f.fish_code, count(*)::int as n_live
      from public.fish f
      join public.fish_tank_memberships m on m.fish_id=f.id and m.left_at is null
      join public.v_tanks_for_fish vt on vt.tank_id = m.container_id
      where c.status = any(:live_statuses) and c.container_type = any(:tank_types)
      group by f.fish_code
    )
    select
      cp.id::text                           as clutch_id,
      coalesce(cp.clutch_code, cp.id::text) as clutch_code,
      coalesce(cp.planned_name,'')          as planned_name,
      coalesce(cp.planned_nickname,'')      as planned_nickname,
      coalesce(ml.n_live,0)                 as mom_live,
      coalesce(dl.n_live,0)                 as dad_live,
      (coalesce(ml.n_live,0)*coalesce(dl.n_live,0))::int as pairings,
      cp.created_by, cp.created_at
    from public.clutch_plans cp
    left join mom_live ml on ml.fish_code = cp.mom_code
    left join dad_live dl on dl.fish_code = cp.dad_code
    where (cp.created_at::date between :d1 and :d2)
      and (:by = '' or cp.created_by ilike :byl)
      and (:q = '' or coalesce(cp.clutch_code,'') ilike :ql or coalesce(cp.planned_name,'') ilike :ql or coalesce(cp.planned_nickname,'') ilike :ql)
    order by cp.created_at desc
    """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={
            "live_statuses": list(LIVE_STATUSES), "tank_types": list(TANK_TYPES),
            "d1": d1, "d2": d2, "by": created_by or "", "byl": f"%{created_by or ''}%",
            "q": q or "", "ql": f"%{q or ''}%"
        })

def _get_concept_id(sel: pd.DataFrame) -> t.Optional[str]:
    return str(sel.iloc[0]["clutch_id"]) if (isinstance(sel, pd.DataFrame) and not sel.empty and "clutch_id" in sel.columns) else None

def _ensure_cross_id(mom_code: str, dad_code: str, created_by_val: str) -> str:
    cols = _table_cols("public","crosses")
    with _get_engine().begin() as cx:
        cross_id = None
        if "mother_code" in cols and "father_code" in cols:
            cross_id = cx.execute(text("""
                select id::text from public.crosses
                where mother_code=:m and father_code=:d
                limit 1
            """), {"m": mom_code, "d": dad_code}).scalar()
        if cross_id:
            return str(cross_id)
        fields, params = [], {}
        if "mother_code" in cols:
            fields.append("mother_code"); params["mother_code"] = mom_code
        if "father_code" in cols:
            fields.append("father_code"); params["father_code"] = dad_code
        if "cross_name" in cols:
            fields.append("cross_name"); params["cross_name"] = f"{mom_code} x {dad_code}"
        if "created_by" in cols:
            fields.append("created_by"); params["created_by"] = created_by_val
        sql = text(f"""
            insert into public.crosses ({", ".join(fields)})
            values ({", ".join(":"+k for k in params.keys())})
            returning id::text
        """)
        return str(cx.execute(sql, params).scalar())

with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1,1,1,3])
    with c1: start = st.date_input("From", value=today - timedelta(days=120))
    with c2: end   = st.date_input("To",   value=today + timedelta(days=14))
    with c3: created_by = st.text_input("Created by", value="")
    with c4: q = st.text_input("Search (code/name/nickname)", value="")
    r1, r2 = st.columns([1,3])
    with r1: most_recent = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", use_container_width=True)

plans = _load_clutch_concepts(start, end, created_by, q)
st.markdown("### 1) Select the clutch genotype you want to generate")
st.caption(f"{len(plans)} clutch concept(s).")
plan_df = plans.copy() if not plans.empty else pd.DataFrame()
if "✓ Select" not in plan_df.columns:
    plan_df.insert(0,"✓ Select",False)
plan_edited = st.data_editor(
    plan_df[["✓ Select","clutch_code","planned_name","planned_nickname","pairings","created_by","created_at"]],
    hide_index=True, use_container_width=True,
    column_config={
        "✓ Select":  st.column_config.CheckboxColumn("✓", default=False),
        "pairings":  st.column_config.NumberColumn("pairings", disabled=True),
        "created_at":st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key="plan_picker",
)
sel_mask  = plan_edited.get("✓ Select", pd.Series(False, index=plan_edited.index)).fillna(False).astype(bool)
sel_plans = plan_df.loc[sel_mask].reset_index(drop=True)
concept_id = _get_concept_id(sel_plans)

st.markdown("### 2) Schedule candidates (saved tank_pairs for this concept)")
if not concept_id:
    st.info("Pick a clutch concept above.")
    tp_edit = pd.DataFrame()
else:
    if not _view_exists("public","v_tank_pairs_overview"):
        st.error("View public.v_tank_pairs_overview not found."); st.stop()
    with _get_engine().begin() as cx:
        tp = pd.read_sql(text("""
          select *
          from public.v_tank_pairs_overview
          where concept_id = :concept
          order by created_at desc
          limit 500
        """), cx, params={"concept": concept_id})
    if tp.empty:
        st.info("No saved tank_pairs for this concept yet.")
        tp_edit = pd.DataFrame()
    else:
        tp = tp.copy()
        tp.insert(0,"✓ Reschedule", False)
        cols = ["✓ Reschedule","tank_pair_code","clutch_code","status",
                "mom_fish_code","mom_tank_code","dad_fish_code","dad_tank_code",
                "id","mother_tank_id","father_tank_id","created_by","created_at"]
        cols = [c for c in cols if c in tp.columns]
        tp_edit = st.data_editor(
            tp[cols], use_container_width=True, hide_index=True, num_rows="fixed",
            column_config={
                "✓ Reschedule":    st.column_config.CheckboxColumn("✓", default=False),
                "tank_pair_code":  st.column_config.TextColumn("tank_pair_code", disabled=True),
                "status":          st.column_config.TextColumn("status", disabled=True),
                "clutch_code":     st.column_config.TextColumn("clutch_code", disabled=True),
                "mom_fish_code":   st.column_config.TextColumn("mom_fish_code", disabled=True),
                "mom_tank_code":   st.column_config.TextColumn("mom_tank_code", disabled=True),
                "dad_fish_code":   st.column_config.TextColumn("dad_fish_code", disabled=True),
                "dad_tank_code":   st.column_config.TextColumn("dad_tank_code", disabled=True),
                "id":              st.column_config.TextColumn("id", disabled=True),
                "mother_tank_id":  st.column_config.TextColumn("mother_tank_id", disabled=True),
                "father_tank_id":  st.column_config.TextColumn("father_tank_id", disabled=True),
                "created_by":      st.column_config.TextColumn("created_by", disabled=True),
                "created_at":      st.column_config.DatetimeColumn("created_at", disabled=True),
            },
            key="tank_pair_candidates",
        )

st.markdown("### 3) Reschedule selected tank_pair(s) → new cross instance(s)")
run_date_all = st.date_input("Run date", value=date.today(), key="run_date_all")
creator_val  = os.environ.get("USER") or os.environ.get("USERNAME") or "system"

flash_here = st.empty()
if _msg:
    if _msg.get("made"):
        flash_here.success(f"Scheduled {len(_msg['made'])} instance(s): {', '.join(_msg['made'])}")
    elif _msg.get("dupes"):
        flash_here.warning("Already scheduled for that date:\n- " + "\n- ".join(_msg["dupes"]))

def _reschedule(rows: pd.DataFrame, concept_id: str, run_date: date, created_by_val: str) -> t.Tuple[t.List[str], t.List[str]]:
    if rows is None or not isinstance(rows, pd.DataFrame) or rows.empty:
        return [], []
    ci_cols = _table_cols("public", "cross_instances")
    have_note = "note" in ci_cols
    have_by   = "created_by" in ci_cols
    have_mom  = "mother_tank_id" in ci_cols
    have_dad  = "father_tank_id" in ci_cols
    have_date = "cross_date" in ci_cols
    have_code = "cross_run_code" in ci_cols
    have_tp   = "tank_pair_id" in ci_cols
    made, dupes = [], []
    with _get_engine().begin() as cx:
        base = pd.read_sql(text("""
          select * from public.v_tank_pairs_overview where concept_id = :c
        """), cx, params={"c": concept_id})
        by_id = {str(r["id"]): r for _, r in base.iterrows()} if not base.empty else {}
        for _, r in rows.iterrows():
            tp = by_id.get(str(r.get("id","")))
            if tp is None:
                continue
            mom_code = str(tp.get("mom_fish_code","") or "")
            dad_code = str(tp.get("dad_fish_code","") or "")
            mom_id   = str(tp.get("mother_tank_id","") or "")
            dad_id   = str(tp.get("father_tank_id","") or "")
            tp_id    = str(tp.get("id","") or "")
            cross_id = _ensure_cross_id(mom_code, dad_code, created_by_val)
            params = {"cross_id": cross_id, "tp_id": tp_id,
                      "mom_id": mom_id, "dad_id": dad_id,
                      "run_date": run_date, "by": created_by_val}
            cols, vals = ["cross_id"], ["cast(:cross_id as uuid)"]
            if have_tp and tp_id: cols += ["tank_pair_id"];   vals += ["cast(:tp_id as uuid)"]
            if have_mom and mom_id: cols += ["mother_tank_id"]; vals += ["cast(:mom_id as uuid)"]
            if have_dad and dad_id: cols += ["father_tank_id"]; vals += ["cast(:dad_id as uuid)"]
            if have_date: cols += ["cross_date"]; vals += [":run_date"]
            if have_by:   cols += ["created_by"]; vals += [":by"]
            if have_note: cols += ["note"];       vals += ["''"]
            insert_sql = f"""
with ins as (
  insert into public.cross_instances ({", ".join(cols)})
  select {", ".join(vals)}
  where not exists (
    select 1 from public.cross_instances ci
    where {"ci.tank_pair_id = cast(:tp_id as uuid) and " if have_tp else ""}ci.cross_date = :run_date
  )
  returning id::uuid as ci_id, coalesce({"cross_run_code" if have_code else "id::text"}, id::text) as cross_run_code
)
select * from ins
"""
            res = cx.execute(text(insert_sql), params).mappings().first()
            if not res:
                dupes.append(f"{tp.get('tank_pair_code','')} already scheduled for {run_date}.")
                continue
            ci_id = res["ci_id"]; cr_code = str(res["cross_run_code"])
            cx.execute(text("""
              insert into public.clutches (cross_id, cross_instance_id, date_birth, planned_cross_id, created_by)
              values (cast(:cross_id as uuid), cast(:ci_id as uuid), (:dt + interval '1 day')::date, cast(:pid as uuid), :by)
              on conflict do nothing
            """), {"cross_id": cross_id, "ci_id": ci_id, "dt": run_date, "pid": concept_id, "by": created_by_val})
            if tp_id:
                cx.execute(text("""
                  update public.tank_pairs
                     set status = 'scheduled', updated_at = now()
                   where id = cast(:id as uuid) and status <> 'scheduled'
                """), {"id": tp_id})
            made.append(cr_code)
    return made, dupes

if concept_id and isinstance(tp_edit, pd.DataFrame) and not tp_edit.empty:
    to_run = tp_edit[tp_edit["✓ Reschedule"] == True].reset_index(drop=True)
    if st.button("↻ Schedule selected tank_pair(s)", type="primary", use_container_width=True, disabled=to_run.empty):
        made, dupes = _reschedule(to_run, concept_id, run_date_all, creator_val)
        if made:
            flash_here.success(f"Scheduled {len(made)} instance(s): {', '.join(made)}")
        if dupes:
            flash_here.warning("Already scheduled for that date:\n- " + "\n- ".join(dupes))
        st.session_state["schedule_result"] = {"made": made, "dupes": dupes}
        st.session_state["last_run_date"] = run_date_all
        st.session_state["last_plan_id"]  = concept_id
        st.rerun()

st.markdown("### 4) Scheduled instances")

last_dt  = st.session_state.pop("last_run_date", None)
last_pid = st.session_state.pop("last_plan_id", None)
d1 = min(start, last_dt) if last_dt else start
d2 = max(end,   last_dt) if last_dt else end
only_this_concept = st.checkbox("Only this concept", value=True, key="only_this_concept")

def _load_recent_clutches(plan_id: t.Optional[str], d1: date, d2: date, ignore_dates: bool, only_this: bool) -> pd.DataFrame:
    if not _view_exists("public","v_clutches_overview_final"):
        return pd.DataFrame()
    where = []
    params: dict = {}
    if plan_id and only_this:
        where.append("clutch_plan_id = cast(:pid as uuid)")
        params["pid"] = plan_id
    if not ignore_dates:
        where.append("coalesce(clutch_birthday, date_planned) between :d1 and :d2")
        params["d1"] = d1; params["d2"] = d2
    where_sql = " AND ".join(where) if where else "true"
    sql = text(f"""
      select
        clutch_code,
        cross_name_pretty,
        clutch_name,
        clutch_genotype_pretty,
        clutch_genotype_canonical,
        mom_genotype, dad_genotype,
        mom_strain, dad_strain, clutch_strain_pretty,
        treatments_count, treatments_pretty,
        clutch_birthday,
        created_by_instance, created_at_instance
      from public.v_clutches_overview_final
      where {where_sql}
      order by created_at_instance desc nulls last, clutch_birthday desc nulls last
      limit 200
    """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params=params)

ci = _load_recent_clutches(concept_id, d1, d2, most_recent, only_this_concept)
if ci.empty and only_this_concept:
    st.info("No scheduled instances for this concept with the current filters. Showing most recent across all concepts.")
    ci = _load_recent_clutches(None, d1, d2, True, False)

if ci.empty:
    st.info("No scheduled instances match the filters.")
else:
    show_cols = [
    "clutch_code",
    "clutch_birthday",
    "cross_name_pretty",
    "genotype_treatment_rollup",   # ← NEW (visible)
    "clutch_genotype_pretty",
    "clutch_genotype_canonical",
    "mom_genotype","dad_genotype",
    "mom_strain","dad_strain","clutch_strain_pretty",
    "treatments_count","treatments_pretty",
    "created_by_instance","created_at_instance",
]
    have_cols = [c for c in show_cols if c in ci.columns]
    st.dataframe(
    ci[have_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "genotype_treatment_rollup": st.column_config.TextColumn(
            "genotype_treatment_rollup",
            help="Formatted as: treatments_pretty > clutch_genotype_pretty"
        )
    },
)