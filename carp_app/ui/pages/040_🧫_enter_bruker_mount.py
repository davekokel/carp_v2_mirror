from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from pathlib import Path
from datetime import date, datetime, time, timezone
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

st.set_page_config(page_title="Enter Bruker Mount", page_icon="🧪", layout="wide")
st.title("🧪 Enter Bruker Mount")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

# ───────────────────────── helpers ─────────────────────────
def _exists(schema_dot_name: str) -> bool:
    sch, tab = schema_dot_name.split(".", 1)
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

def _load_concepts(q: str, limit: int) -> pd.DataFrame:
    if not _exists("public.v_cross_concepts_overview"):
        st.error("Missing view public.v_cross_concepts_overview."); st.stop()
    base = """
      select
        conceptual_cross_code as clutch_code,
        name                  as clutch_name,
        nickname              as clutch_nickname,
        mom_code, dad_code, mom_code_tank, dad_code_tank,
        created_at
      from public.v_cross_concepts_overview
    """
    where = ""
    params = {}
    if q:
        where = """
          where (conceptual_cross_code ilike %(q)s
             or name ilike %(q)s
             or nickname ilike %(q)s
             or mom_code ilike %(q)s
             or dad_code ilike %(q)s)
        """
        params["q"] = f"%{q.strip()}%"
    sql = f"""
      {base}
      {where}
      order by created_at desc nulls last, conceptual_cross_code
      limit %(lim)s
    """
    params["lim"] = int(limit)
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params=params)

def _runs_for_clutch(clutch_code: str, limit: int = 100) -> pd.DataFrame:
    sql = """
      select
        ci.cross_run_code,
        ci.clutch_birthday as birthday,
        cm.tank_code as mother_tank_label,
        cf.tank_code as father_tank_label,
        count(sel.id)::int as selections_rollup
      from public.clutch_plans cp
      join public.planned_crosses pc  on pc.clutch_id = cp.id
      join public.crosses x           on x.id = pc.cross_id
      join public.cross_instances ci  on ci.cross_id = x.id
      left join public.containers cm  on cm.id = coalesce(ci.mother_tank_id, pc.mother_tank_id)
      left join public.containers cf  on cf.id = coalesce(ci.father_tank_id, pc.father_tank_id)
      left join public.clutch_instances sel on sel.cross_instance_id = ci.id
      where cp.clutch_code = %(code)s
      group by ci.id, ci.cross_run_code, ci.clutch_birthday, cm.tank_code, cf.tank_code
      order by ci.clutch_birthday desc, ci.created_at desc nulls last
      limit %(lim)s
    """
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params={"code": clutch_code, "lim": int(limit)})

def _resolve_cross_instance_id(run_code: str) -> Optional[str]:
    with eng.begin() as cx:
        xid = pd.read_sql(
            "select id::text as cross_instance_id from public.cross_instances where cross_run_code = %(rc)s limit 1",
            cx, params={"rc": run_code}
        )
    return None if xid.empty else xid["cross_instance_id"].iloc[0]

def _load_mounts_for_run(run_code: str) -> pd.DataFrame:
    sql = """
      select
        mount_code,
        mount_date, time_mounted, mounting_orientation,
        n_top, n_bottom,
        sample_id, mount_type, notes,
        created_at, created_by
      from public.mounts
      where cross_instance_id = (
        select id from public.cross_instances where cross_run_code = %(rc)s limit 1
      )
      order by coalesce(time_mounted, mount_date::timestamptz, created_at) desc nulls last
    """
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params={"rc": run_code})

# ───────────────────────── page layout ─────────────────────────
st.caption("DB: " + (getattr(getattr(eng, "url", None), "host", None) or os.getenv("PGHOST", "(unknown)"))
           + " • role=" + (getattr(user, "role", None) or "none")
           + " • user=" + (getattr(user, "email", None) or "postgres"))

# 1) Choose clutch concept
st.header("1) Choose clutch concept")
with st.form("concept_filters"):
    c1, c2 = st.columns([3,1])
    q  = c1.text_input("Filter concepts (code/name/mom/dad)", placeholder="e.g., CL-25 or MGCO or FSH-250001")
    lim = int(c2.number_input("Show up to", min_value=10, max_value=2000, value=500, step=10))
    _ = st.form_submit_button("Apply")

concepts = _load_concepts(q or "", lim)
if concepts.empty:
    st.info("No clutch concepts match."); st.stop()

key_concepts = "_bruker_concepts"
if key_concepts not in st.session_state:
    t = concepts.copy()
    t.insert(0, "✓", False)
    st.session_state[key_concepts] = t
else:
    base = st.session_state[key_concepts].set_index("clutch_code")
    now  = concepts.set_index("clutch_code")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
        else:
            for col in now.columns:
                if col != "✓":
                    base.at[i, col] = now.at[i, col]
    base = base.loc[now.index]
    st.session_state[key_concepts] = base.reset_index()

present = ["✓","clutch_code","clutch_name","clutch_nickname","mom_code","dad_code","created_at"]
edited_concepts = st.data_editor(
    st.session_state[key_concepts][present],
    hide_index=True, use_container_width=True,
    column_order=present,
    column_config={
        "✓": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code": st.column_config.TextColumn("clutch_code", disabled=True),
        "clutch_name": st.column_config.TextColumn("clutch_name", disabled=True),
        "clutch_nickname": st.column_config.TextColumn("clutch_nickname", disabled=True),
        "mom_code": st.column_config.TextColumn("mom_code", disabled=True),
        "dad_code": st.column_config.TextColumn("dad_code", disabled=True),
        "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key="concepts_editor",
)
st.session_state[key_concepts].loc[edited_concepts.index, "✓"] = edited_concepts["✓"]

sel_codes = edited_concepts.loc[edited_concepts["✓"] == True, "clutch_code"].astype(str).tolist()
if not sel_codes:
    st.info("Tick a clutch concept to continue."); st.stop()
if len(sel_codes) > 1:
    st.warning("Tick exactly **one** clutch concept to continue."); st.stop()

clutch_code = sel_codes[0]

# reset runs state if selected clutch changes
if st.session_state.get("_bruker_runs_clutch") != clutch_code:
    st.session_state["_bruker_runs_clutch"] = clutch_code
    st.session_state.pop("_bruker_runs", None)

# 2) Choose cross instance (run) for the concept
st.header("2) Choose cross instance (run) for the concept")
runs = _runs_for_clutch(clutch_code, limit=200)
st.caption(f"DBG • clutch={clutch_code} • runs_found={len(runs)}")
if runs.empty:
    st.caption("empty")
    st.info("No realized runs exist for this concept yet.")
    st.stop()

key_runs = "_bruker_runs"
if key_runs not in st.session_state or st.session_state[key_runs].empty:
    t = runs.copy()
    t.insert(0, "✓", False)
    st.session_state[key_runs] = t
else:
    base = st.session_state[key_runs].set_index("cross_run_code")
    now  = runs.set_index("cross_run_code")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
        else:
            for col in now.columns:
                if col != "✓":
                    base.at[i, col] = now.at[i, col]
    base = base.loc[now.index]
    st.session_state[key_runs] = base.reset_index()

present_runs = ["✓","cross_run_code","birthday","mother_tank_label","father_tank_label","selections_rollup"]
edited_runs = st.data_editor(
    st.session_state[key_runs][present_runs],
    hide_index=True, use_container_width=True,
    column_order=present_runs,
    column_config={
        "✓": st.column_config.CheckboxColumn("✓", default=False),
        "cross_run_code":   st.column_config.TextColumn("cross_run_code", disabled=True),
        "birthday":         st.column_config.DateColumn("clutch_birthday", disabled=True),
        "mother_tank_label":st.column_config.TextColumn("mother_tank_label", disabled=True),
        "father_tank_label":st.column_config.TextColumn("father_tank_label", disabled=True),
        "selections_rollup":st.column_config.NumberColumn("# selections", disabled=True, step=1, format="%d"),
    },
    key="runs_editor",
)
st.session_state[key_runs].loc[edited_runs.index, "✓"] = edited_runs["✓"]

picked = edited_runs.loc[edited_runs["✓"] == True, "cross_run_code"].astype(str).tolist()
if len(picked) == 0:
    st.info("Tick exactly one run to continue."); st.stop()
if len(picked) > 1:
    st.warning("Tick exactly one run to continue."); st.stop()

run_code = picked[0]

# 3) Enter mount metadata (all requested fields)
st.header("3) Enter mount metadata")
if not _exists("public.mounts"):
    st.error("Table public.mounts not found. Add it before using this page.")
    st.caption("""Expected columns:
      id uuid PK, cross_instance_id uuid FK → cross_instances(id),
      mount_date date, time_mounted timestamptz, mounting_orientation text,
      n_top int, n_bottom int, sample_id text, mount_type text, notes text,
      created_at timestamptz default now(), created_by text""")
    st.stop()

c1, c2, c3 = st.columns([1,1,2])
with c1:
    mount_date = st.date_input("Mount date", value=date.today())
with c2:
    mount_type = st.selectbox("Mount type", ["larva","juvenile","adult","other"])
with c3:
    sample_id = st.text_input("Sample identifier (Bruker slide or series)", value="", placeholder="e.g., SLIDE-20251016-01")

c4, c5, c6 = st.columns([1,1,1])
with c4:
    mount_time = st.time_input("Time mounted (optional)", value=time(0, 0))
with c5:
    mounting_orientation = st.selectbox("Mounting orientation", ["dorsal_up","ventral_up","lateral_left","lateral_right","other"])
with c6:
    n_top = st.number_input("n_top (optional)", min_value=0, value=0, step=1)
    n_bottom = st.number_input("n_bottom (optional)", min_value=0, value=0, step=1)

notes = st.text_area("Notes", value="", placeholder="Mount prep, imaging settings, etc.")

can_save = bool(run_code and mount_date and (sample_id.strip() != ""))
save_btn = st.button("Save mount", type="primary", use_container_width=True, disabled=not can_save)

if save_btn:
    xid = _resolve_cross_instance_id(run_code)
    if not xid:
        st.error(f"Couldn’t resolve cross_instance_id for {run_code}")
    else:
        tm_ts = None
        try:
            dt_local = datetime.combine(mount_date, mount_time or time(0, 0))
            tm_ts = dt_local.replace(tzinfo=timezone.utc)  # change TZ here if you prefer local
        except Exception:
            tm_ts = None

        with eng.begin() as cx:
            cx.execute(
                text("""
                  insert into public.mounts (
                    cross_instance_id, mount_date, time_mounted,
                    sample_id, mount_type, mounting_orientation,
                    n_top, n_bottom, notes, created_by
                  )
                  values (
                    cast(:xid as uuid), :mount_date, :time_mounted,
                    :sample_id, :mount_type, :mounting_orientation,
                    :n_top, :n_bottom, :notes,
                    coalesce(current_setting('app.user', true), :by)
                  )
                """),
                {
                    "xid": xid,
                    "mount_date": mount_date,
                    "time_mounted": tm_ts,
                    "sample_id": sample_id.strip(),
                    "mount_type": mount_type,
                    "mounting_orientation": mounting_orientation,
                    "n_top": int(n_top or 0),
                    "n_bottom": int(n_bottom or 0),
                    "notes": notes.strip(),
                    "by": (getattr(user, "email", "") or "unknown"),
                }
            )
        st.success(f"✅ Mount saved for run {run_code}")
        st.rerun()

# 4) Existing mounts for this run (show all requested fields incl. mount_code)
# 4) Existing mounts for this run (show all requested fields incl. mount_label)
st.subheader("Existing mounts for this run")
mounts = pd.read_sql(
    """
      select
        mount_label,                                  -- ← human label MT-YYYY-MM-DD #N
        mount_date, time_mounted, mounting_orientation,
        n_top, n_bottom,
        sample_id, mount_type, notes,
        created_at, created_by
      from public.mounts
      where cross_instance_id = (
        select id from public.cross_instances
        where cross_run_code = %(rc)s
        limit 1
      )
      order by coalesce(time_mounted, mount_date::timestamptz, created_at) desc nulls last
    """,
    eng, params={"rc": run_code}
)

if mounts.empty:
    st.caption("No mounts logged for this run yet.")
else:
    cols = [
        "mount_label",
        "mount_date","time_mounted","mounting_orientation",
        "n_top","n_bottom",
        "sample_id","mount_type","notes",
        "created_at","created_by"
    ]
    st.dataframe(mounts[[c for c in cols if c in mounts.columns]],
                 hide_index=True, use_container_width=True)