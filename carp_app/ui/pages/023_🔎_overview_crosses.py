from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from pathlib import Path
from typing import List, Tuple

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
st.title("🔎 Overview — Crosses")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

def _status_badge(s: str) -> str:
    s = (s or "").lower().strip()
    return {
        "draft": "🟣 draft",
        "ready": "🟢 ready",
        "scheduled": "🔵 scheduled",
        "closed": "⚫ closed",
    }.get(s, s or "")

with st.form("filters"):
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    q  = c1.text_input("Search (code/name/nickname/mom/dad)")
    d1 = c2.date_input("From", value=None)
    d2 = c3.date_input("To", value=None)
    status_filter = c4.selectbox("Status", ["(any)","draft","ready","scheduled","closed"], index=0)
    runnable_only = st.toggle("Runnable only (both parents have live tanks)", value=False)
    show_clutch_instances = st.toggle("Show clutch instances under each run", value=False)
    _ = st.form_submit_button("Apply")

where_parts, params = [], {}
if q:
    where_parts.append("(clutch_code ilike :q or name ilike :q or nickname ilike :q or mom_code ilike :q or dad_code ilike :q)")
    params["q"] = f"%{q.strip()}%"
if d1:
    where_parts.append("created_at >= :d1"); params["d1"] = str(d1)
if d2:
    where_parts.append("created_at <= :d2"); params["d2"] = str(d2)
if status_filter != "(any)":
    where_parts.append("status = :st"); params["st"] = status_filter
if runnable_only:
    where_parts.append("runnable is true")
where_sql = (" where " + " and ".join(where_parts)) if where_parts else ""

sql = text(f"""
  select *
  from public.v_overview_crosses
  {where_sql}
  order by created_at desc nulls last
  limit 500
""")
with eng.begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption("concepts: v_overview_crosses (name=codes, nickname=genotype)  |  instances: cross_instances via planned_crosses.cross_id")
st.caption(f"{len(df)} planned clutch(es)")
if df.empty:
    st.info("No planned clutches match."); st.stop()

# session table with selection + status badge
key = "_cross_concepts"
def _new_session_table() -> pd.DataFrame:
    t = df.copy()
    t.insert(0, "✓ Select", False)
    t["status_badge"] = t["status"].map(_status_badge) if "status" in t.columns else ""
    return t

if key not in st.session_state:
    st.session_state[key] = _new_session_table()
else:
    # realign to latest df, preserving checkboxes for kept rows
    base = st.session_state[key].set_index("clutch_code", drop=False)
    now = df.copy()
    now["status_badge"] = now["status"].map(_status_badge) if "status" in now.columns else ""
    now = now.set_index("clutch_code", drop=False)
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
        else:
            # refresh non-selection fields from latest
            for c in now.columns:
                if c != "✓ Select":
                    base.at[i, c] = now.at[i, c]
    base = base.loc[now.index]
    st.session_state[key] = base.reset_index(drop=True)

concept_cols = [
    "✓ Select",
    "clutch_code",
    "name",
    "nickname",
    "mom_code",
    "dad_code",
    "created_at",
    "status_badge",
    "planned_count",
    "runnable",
]
present = [c for c in concept_cols if c in st.session_state[key].columns]
edited = st.data_editor(
    st.session_state[key][present],
    hide_index=True,
    use_container_width=True,
    column_order=present,
    column_config={
        "✓ Select":      st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code":   st.column_config.TextColumn("Clutch", disabled=True),
        "name":          st.column_config.TextColumn("Cross (codes)", disabled=True),
        "nickname":      st.column_config.TextColumn("Cross (genotype)", disabled=True),
        "mom_code":      st.column_config.TextColumn("Mom", disabled=True),
        "dad_code":      st.column_config.TextColumn("Dad", disabled=True),
        "created_at":    st.column_config.DatetimeColumn("Created", disabled=True),
        "status_badge":  st.column_config.TextColumn("Status", disabled=True, help="draft/ready/scheduled/closed"),
        "planned_count": st.column_config.NumberColumn("Planned Crosses", disabled=True, step=1, format="%d"),
        "runnable":      st.column_config.CheckboxColumn("Runnable", disabled=True),
    },
    key="crosses_editor",
)
if "✓ Select" in edited.columns:
    st.session_state[key].loc[edited.index, "✓ Select"] = edited["✓ Select"]

sel_codes: List[str] = edited.loc[edited.get("✓ Select", False) == True, "clutch_code"].astype(str).tolist()
if not sel_codes:
    st.info("Select one or more planned clutches to show existing instances.")
    st.stop()

st.divider()
st.subheader("Existing cross instances")

def _fetch_instances_for_concept(code: str) -> Tuple[pd.DataFrame, str | None]:
    with eng.begin() as cx:
        cp = pd.read_sql(
            text("select id from public.clutch_plans where clutch_code = :code limit 1"),
            cx, params={"code": code}
        )
        if cp.empty:
            return pd.DataFrame(), "No clutch_plans row for this clutch_code."

        pc = pd.read_sql(
            text("""
                select id, cross_id, created_at, mother_tank_id, father_tank_id, created_by
                from public.planned_crosses
                where clutch_id = :cid
                order by created_at desc
                limit 1000
            """),
            cx, params={"cid": cp["id"].iloc[0]}
        )
        if pc.empty:
            return pd.DataFrame(), "No planned_crosses rows for this concept."
        if pc["cross_id"].isna().all():
            return pd.DataFrame(), "planned_crosses exist but cross_id is NULL (not linked to a cross)."

        runs = pd.read_sql(
            text("""
                select
                  ci.cross_run_code,
                  ci.cross_date,
                  x.mother_code  as mom_code,
                  x.father_code  as dad_code,
                  cm.tank_code   as mom_tank,
                  cf.tank_code   as dad_tank,
                  coalesce(ci.created_by, pc.created_by) as created_by,
                  coalesce(ci.created_at, pc.created_at) as created_at,
                  coalesce(
                    nullif(to_jsonb(ci)->>'run_note',''),
                    nullif(to_jsonb(ci)->>'note',''),
                    nullif(to_jsonb(ci)->>'notes','')
                  ) as note,
                  ci.id as cross_instance_id
                from public.planned_crosses pc
                join public.crosses x          on x.id = pc.cross_id
                join public.cross_instances ci on ci.cross_id = x.id
                left join public.containers cm on cm.id = coalesce(ci.mother_tank_id, pc.mother_tank_id)
                left join public.containers cf on cf.id = coalesce(ci.father_tank_id, pc.father_tank_id)
                where pc.clutch_id = :cid
                order by coalesce(ci.created_at, pc.created_at) desc nulls last,
                         ci.cross_date desc nulls last
                limit 1000
            """),
            cx, params={"cid": cp["id"].iloc[0]}
        )
        if runs.empty:
            return pd.DataFrame(), "Linked planned_crosses/crosses found, but no cross_instances yet."
        return runs, None

def _fetch_clutch_instances(cross_instance_id: str) -> pd.DataFrame:
    with eng.begin() as cx:
        return pd.read_sql(
            text("""
                select
                  ci.id as clutch_instance_id,
                  ci.label,
                  ci.red_intensity,
                  ci.green_intensity,
                  ci.notes,
                  ci.annotated_by,
                  ci.annotated_at,
                  ci.created_at
                from public.clutch_instances ci
                where ci.cross_instance_id = cast(:xid as uuid)
                order by coalesce(ci.annotated_at, ci.created_at) desc,
                         ci.created_at desc
            """),
            cx, params={"xid": cross_instance_id}
        )

any_found = False
for code in sel_codes:
    st.markdown(f"**{code}**")
    try:
        runs, warn = _fetch_instances_for_concept(code)
    except Exception as e:
        st.warning(f"Failed for {code}: {e}")
        st.markdown("---")
        continue

    if warn:
        st.info(warn)
        st.markdown("---")
        continue

    if runs.empty:
        st.caption("No instances.")
        st.markdown("---")
        continue

    any_found = True

    show = ["cross_run_code","cross_date","mom_code","dad_code","mom_tank","dad_tank","created_by","created_at","note"]
    st.dataframe(runs[[c for c in show if c in runs.columns]], use_container_width=True, hide_index=True)

    st.caption("Actions")
    for _idx, r in runs.iterrows():
        cc = st.columns([2, 3, 3, 6])
        with cc[0]:
            if st.button("Annotate 📝", key=f"ann_{code}_{r['cross_run_code']}"):
                st.session_state["annotate_prefill_run"] = r["cross_run_code"]
                st.session_state["annotate_prefill_run"] = r["cross_run_code"]
                st.switch_page("pages/034_🐣_annotate_clutch_instances.py")
        with cc[1]:
            st.write(f"`{r['cross_run_code']}`")
        with cc[2]:
            st.write(str(r.get("cross_date") or ""))
        with cc[3]:
            st.write(f"{r.get('mom_code','')} × {r.get('dad_code','')}")

        if show_clutch_instances and pd.notna(r.get("cross_instance_id")):
            with st.expander(f"Clutch selections for {r['cross_run_code']}", expanded=False):
                childs = _fetch_clutch_instances(str(r["cross_instance_id"]))
                if childs.empty:
                    st.caption("No clutch selections yet.")
                else:
                    child_cols = ["clutch_instance_id","label","red_intensity","green_intensity","notes","annotated_by","annotated_at","created_at"]
                    st.dataframe(childs[[c for c in child_cols if c in childs.columns]], use_container_width=True, hide_index=True)

    st.markdown("---")

if not any_found:
    st.info("No instance rows found for selected concept(s).")