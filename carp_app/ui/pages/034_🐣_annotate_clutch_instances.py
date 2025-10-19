from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os, re
from pathlib import Path
from typing import List, Optional

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

st.set_page_config(page_title="Annotate Clutch Instances", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Clutch Instances")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

PAGE_SIZE = 50  # rows per "Load more" page

# ───────────────────────── helpers ─────────────────────────
def _exists(full: str) -> bool:
    sch, tab = full.split(".", 1)
    q = text("""
      with t as (
        select table_schema as s, table_name as t from information_schema.tables
        union all
        select table_schema as s, table_name as t from information_schema.views
      )
      select exists(select 1 from t where s=:s and t=:t) as ok
    """)
    with eng.begin() as cx:
        return bool(pd.read_sql(q, cx, params={"s": sch, "t": tab})["ok"].iloc[0])

def _load_concepts() -> pd.DataFrame:
    if not _exists("public.v_cross_concepts_overview"):
        st.error("View public.v_cross_concepts_overview not found. Run the migration first.")
        st.stop()
    with eng.begin() as cx:
        return pd.read_sql(
            text("""
              select
                conceptual_cross_code as clutch_code,
                name                  as clutch_name,
                nickname              as clutch_nickname,
                mom_code, dad_code, mom_code_tank, dad_code_tank,
                created_at
              from public.v_cross_concepts_overview
              order by created_at desc nulls last, conceptual_cross_code
              limit 2000
            """),
            cx,
        )

def _fetch_runs_page(eng, codes: List[str], offset: int, limit: int) -> pd.DataFrame:
    """
    Newest-first realized runs for selected clutches.
    """
    sql = """
    select
      cp.clutch_code,
      ci.cross_run_code,
      ci.cross_date,
      ci.clutch_birthday as birthday,
      x.mother_code        as mom_code,
      x.father_code        as dad_code,
      cm.tank_code         as mother_tank_code,
      cf.tank_code         as father_tank_code,
      cp.planned_name      as clutch_name,
      cp.planned_nickname  as clutch_nickname
    from public.cross_instances ci
    join public.crosses x           on x.id = ci.cross_id
    join public.planned_crosses pc  on pc.cross_id = x.id
    join public.clutch_plans cp     on cp.id = pc.clutch_id
    left join public.containers cm  on cm.id = coalesce(ci.mother_tank_id, pc.mother_tank_id)
    left join public.containers cf  on cf.id = coalesce(ci.father_tank_id, pc.father_tank_id)
    where cp.clutch_code = any(%(codes)s::text[])
    order by ci.clutch_birthday desc, ci.cross_date desc, ci.created_at desc nulls last
    limit %(limit)s offset %(offset)s
    """
    params = {"codes": codes or [], "limit": int(limit), "offset": int(offset)}
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params=params)

def _resolve_cross_instance_by_prefill(run_code: Optional[str], xid: Optional[str]) -> pd.DataFrame:
    cond, params = "", {}
    if xid:
        cond = "and ci.id = cast(:xid as uuid)"
        params["xid"] = xid
    elif run_code:
        cond = "and ci.cross_run_code = :rc"
        params["rc"] = run_code
    else:
        return pd.DataFrame(columns=["cross_instance_id","cross_run_code","cross_date","clutch_birthday","clutch_code"])
    q = f"""
      select
        ci.id::text        as cross_instance_id,
        ci.cross_run_code,
        ci.cross_date,
        ci.clutch_birthday,
        cp.clutch_code
      from public.cross_instances ci
      join public.crosses x          on x.id = ci.cross_id
      join public.planned_crosses pc on pc.cross_id = x.id
      join public.clutch_plans cp    on cp.id = pc.clutch_id
      where 1=1 {cond}
      order by ci.created_at desc nulls last
      limit 1
    """
    with eng.begin() as cx:
        return pd.read_sql(text(q), cx, params=params)

def _resolve_cross_instance_ids(engine, rows: pd.DataFrame) -> List[str]:
    if rows.empty:
        return []
    codes = rows["cross_run_code"].dropna().astype(str).unique().tolist()
    if not codes:
        return []
    sql = """
      select id::text as cross_instance_id, cross_run_code
      from public.cross_instances
      where cross_run_code = any(%(codes)s::text[])
    """
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    if df.empty:
        return []
    merged = rows.merge(df, on="cross_run_code", how="left")
    return merged["cross_instance_id"].dropna().astype(str).tolist()

# ───────────────────────── Prefill handoff ─────────────────────────
prefill_run = st.session_state.pop("annotate_prefill_run", None)
prefill_xid = st.session_state.pop("annotate_prefill_xid", None)

prefill_row = None
if prefill_run or prefill_xid:
    res = _resolve_cross_instance_by_prefill(prefill_run, prefill_xid)
    if not res.empty:
        prefill_row = res.iloc[0]
        st.session_state["__prefill_clutch"] = prefill_row["clutch_code"]
        st.session_state["__prefill_run"]    = prefill_row["cross_run_code"]
        st.success(f"Prefilled: run {prefill_row['cross_run_code']} ({prefill_row['clutch_code']})")

# ───────────────────────── Concept table ─────────────────────────
concept_df = _load_concepts()
if concept_df.empty:
    st.info("No clutch concepts found."); st.stop()

sel_key = "_concept_table"
if sel_key not in st.session_state:
    t = concept_df.copy()
    t.insert(0, "✓ Select", False)
    st.session_state[sel_key] = t
else:
    base = st.session_state[sel_key].set_index("clutch_code")
    now  = concept_df.set_index("clutch_code")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[sel_key] = base.reset_index()

# preselect the clutch from prefill (if any)
if prefill_row is not None and "✓ Select" in st.session_state[sel_key].columns:
    mask = st.session_state[sel_key]["clutch_code"].astype(str).eq(st.session_state["__prefill_clutch"])
    if mask.any():
        st.session_state[sel_key].loc[:, "✓ Select"] = False
        st.session_state[sel_key].loc[mask, "✓ Select"] = True

st.markdown("## 🔍 Clutches — Conceptual overview")
present_cols = [
    "✓ Select","clutch_code","clutch_name","clutch_nickname",
    "mom_code","dad_code","mom_code_tank","dad_code_tank","created_at",
]
present = [c for c in present_cols if c in st.session_state[sel_key].columns]
edited_concepts = st.data_editor(
    st.session_state[sel_key][present],
    hide_index=True,
    use_container_width=True,
    column_order=present,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
    key="ci_concept_editor",
)
st.session_state[sel_key].loc[edited_concepts.index, "✓ Select"] = edited_concepts["✓ Select"]

selected_codes: List[str] = []
tbl = st.session_state.get(sel_key)
if isinstance(tbl, pd.DataFrame):
    selected_codes = tbl.loc[tbl["✓ Select"] == True, "clutch_code"].astype(str).tolist()

# If prefill exists but user hasn't selected anything yet, force-select the prefill clutch
if not selected_codes and prefill_row is not None:
    selected_codes = [st.session_state.get("__prefill_clutch")]

# Strict: require a clutch selection to show runs
st.markdown("### Realized instances (newest first)")
if not selected_codes:
    st.info("Select one or more clutches above to see realized instances.")
    st.stop()

# ───────────────────────── Infinite scroll runs table ─────────────────────────
codes_key = "__runs_codes_key"
if codes_key not in st.session_state or st.session_state[codes_key] != tuple(selected_codes):
    st.session_state[codes_key] = tuple(selected_codes)
    st.session_state["__runs_offset"] = 0
    st.session_state["__runs_df"] = pd.DataFrame()

offset = int(st.session_state.get("__runs_offset", 0))
runs_df = st.session_state.get("__runs_df", pd.DataFrame())

if runs_df.empty:
    page = _fetch_runs_page(eng, selected_codes, offset=0, limit=PAGE_SIZE)
    st.session_state["__runs_df"] = page.copy()
    st.session_state["__runs_offset"] = PAGE_SIZE
    runs_df = page.copy()

# Ensure selection column
if "✓ Add" not in runs_df.columns:
    runs_df.insert(0, "✓ Add", False)

# Pre-check the prefilled run if present in the current list
if prefill_row is not None and "cross_run_code" in runs_df.columns:
    m = runs_df["cross_run_code"].astype(str).eq(str(st.session_state.get("__prefill_run", "")))
    if m.any():
        runs_df.loc[m, "✓ Add"] = True

# Render runs editor
cols = [
    "✓ Add",
    "clutch_code","cross_run_code","birthday",
    "mom_code","dad_code","mother_tank_code","father_tank_code",
]
present_det = [c for c in cols if c in runs_df.columns]
edited_seed = st.data_editor(
    runs_df[present_det],
    hide_index=True,
    use_container_width=True,
    column_order=present_det,
    column_config={"✓ Add": st.column_config.CheckboxColumn("✓", default=False)},
    key="ci_runs_editor_from_view",
)

# Persist edited checkboxes
runs_df.loc[edited_seed.index, "✓ Add"] = edited_seed["✓ Add"]
st.session_state["__runs_df"] = runs_df

# Load more
if st.button("Load more"):
    more = _fetch_runs_page(eng, selected_codes, offset=st.session_state["__runs_offset"], limit=PAGE_SIZE)
    if not more.empty:
        more = more.copy()
        if "✓ Add" not in more.columns:
            more.insert(0, "✓ Add", False)
        st.session_state["__runs_df"] = pd.concat([st.session_state["__runs_df"], more], ignore_index=True)
        st.session_state["__runs_offset"] += PAGE_SIZE
    else:
        st.info("No more runs.")

# ───────────────────────── Only allow annotation after a run is selected ─────────────────────────
checked = st.session_state["__runs_df"].loc[st.session_state["__runs_df"]["✓ Add"] == True]
if checked.empty:
    st.markdown("#### Quick annotate selected")
    st.info("Select one or more runs above to enable annotation.")
    st.markdown("### Selection instances (distinct)")
    st.caption("Select rows above to see their existing selection instances here.")
    st.stop()

# ───────────────────────── Quick annotate selected ─────────────────────────
st.markdown("#### Quick annotate selected")
c1, c2, c3 = st.columns([1,1,3])
with c1:
    red_txt = st.text_input("red", value="", placeholder="text")
with c2:
    green_txt = st.text_input("green", value="", placeholder="text")
with c3:
    note_txt = st.text_input("note", value="", placeholder="optional")

if st.button("Submit"):
    xids = _resolve_cross_instance_ids(eng, checked)
    if not xids:
        st.error("Couldn’t resolve any cross_instance_id from the selected rows.")
    else:
        saved = 0
        with eng.begin() as cx:
            for xid in xids:
                base_label = " / ".join(
                    s for s in {
                        checked.get("clutch_code", pd.Series([""])).iloc[0] if "clutch_code" in checked.columns else "",
                        checked.get("cross_run_code", pd.Series([""])).iloc[0] if "cross_run_code" in checked.columns else "",
                    } if s
                ) or "clutch"
                existing = cx.execute(
                    text("select count(*) from public.clutch_instances where cross_instance_id = cast(:xid as uuid)"),
                    {"xid": xid}
                ).scalar_one_or_none() or 0
                suffix = f" [{existing + 1}]" if existing > 0 else ""
                label  = base_label + suffix
                cx.execute(text("""
                    insert into public.clutch_instances (
                        cross_instance_id, label, created_at,
                        red_intensity, green_intensity, notes,
                        red_selected, green_selected,
                        annotated_by, annotated_at
                    )
                    values (
                        cast(:xid as uuid), :label, now(),
                        nullif(:red,''), nullif(:green,''), nullif(:note,''),
                        case when nullif(:red,'')   is not null then true else false end,
                        case when nullif(:green,'') is not null then true else false end,
                        coalesce(current_setting('app.user', true), :fallback_user),
                        now()
                    )
                """), {
                    "xid": xid,
                    "label": label,
                    "red":   red_txt,
                    "green": green_txt,
                    "note":  note_txt,
                    "fallback_user": (getattr(st, "experimental_user", None).email
                                      if hasattr(st, "experimental_user") and getattr(st.experimental_user, "email", None)
                                      else (getattr(user, "email", "") or "")),
                })
                saved += 1
        st.success(f"Created {saved} clutch instance(s).")
        st.rerun()

# ───────────────────────── Selection instances (distinct) ─────────────────────────
st.markdown("### Selection instances (distinct)")
# Pull codes for selected runs and show human code instead of IDs
xids_prefilled = _resolve_cross_instance_ids(eng, checked)
if xids_prefilled:
    values_all = ", ".join([f"(uuid '{x}')" for x in xids_prefilled])
    sql_all = f"""
        with picked(id) as (values {values_all})
        select
          ci.id           as selection_id,
          ci.cross_instance_id,
          ci.clutch_instance_code,                    -- human code
          ci.created_at   as selection_created_at,
          ci.annotated_at as selection_annotated_at,
          ci.red_intensity,
          ci.green_intensity,
          ci.notes,
          ci.annotated_by,
          ci.label
        from public.clutch_instances ci
        join picked p on p.id = ci.cross_instance_id
        order by coalesce(ci.annotated_at, ci.created_at) desc,
                 ci.created_at desc
    """
    with eng.begin() as cx:
        table_all = pd.read_sql(sql_all, cx)

    if not table_all.empty:
        display_cols = [
            "clutch_instance_code",     # human-friendly ID
            "selection_created_at","selection_annotated_at",
            "red_intensity","green_intensity","notes","annotated_by","label",
        ]
        present = [c for c in display_cols if c in table_all.columns]
        st.dataframe(table_all[present], hide_index=True, use_container_width=True)
else:
    st.caption("No prior selection rows for the checked run(s).")