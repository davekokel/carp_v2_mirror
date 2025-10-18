from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.lib.config import engine as get_engine

sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🐣 Nursery intake", page_icon="🐣", layout="wide")
st.title("🐣 Nursery intake")

_ENGINE = None
def _eng():
    global _ENGINE
    if _ENGINE: return _ENGINE
    url = os.getenv("DB_URL")
    if not url: st.error("DB_URL not set"); st.stop()
    _ENGINE = get_engine()
    return _ENGINE

def _col_exists(schema: str, table: str, col: str) -> bool:
    with _eng().begin() as cx:
        q = text("""select 1 from information_schema.columns where table_schema=:s and table_name=:t and column_name=:c limit 1""")
        return bool(pd.read_sql(q, cx, params={"s": schema, "t": table, "c": col}).shape[0])

def _table_exists(schema: str, table: str) -> bool:
    with _eng().begin() as cx:
        q = text("""select 1 from information_schema.tables where table_schema=:s and table_name=:t limit 1""")
        return bool(pd.read_sql(q, cx, params={"s": schema, "t": table}).shape[0])

def _load_instances(d1: date, d2: date, created_by: str, q: str) -> pd.DataFrame:
    sql = text("""
      select
        ci.id::text         as cross_instance_id,
        ci.cross_run_code   as cross_run,
        ci.cross_date,
        x.cross_code,
        coalesce(x.cross_name_code, x.cross_code)    as cross_name,
        coalesce(x.cross_name_genotype,'')           as cross_name_genotype,
        cl.id::text         as clutch_id,
        coalesce(cl.clutch_instance_code, left(cl.id::text,8)) as clutch_code,
        cl.date_birth,
        ci.created_by,
        ci.created_at
      from public.cross_instances ci
      join public.crosses x on x.id = ci.cross_id
      left join public.clutches cl on cl.cross_instance_id = ci.id
      where (ci.cross_date between :d1 and :d2)
        and (:by = '' or ci.created_by ilike :byl)
        and (
          :q = '' or
          ci.cross_run_code ilike :ql or
          x.cross_code ilike :ql or
          coalesce(x.cross_name_code,'') ilike :ql or
          coalesce(x.cross_name_genotype,'') ilike :ql or
          coalesce(cl.clutch_instance_code, left(cl.id::text,8)) ilike :ql
        )
      order by ci.cross_date desc, ci.created_at desc
      limit 500
    """)
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params={"d1": d1, "d2": d2, "by": created_by or "", "byl": f"%{created_by or ''}%", "q": q or "", "ql": f"%{q or ''}%"})

with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=7))
    with c2: d2 = st.date_input("To", value=today)
    with c3: created_by = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "")
    with c4: q = st.text_input("Search (run/genotype/clutch)", value="")
    st.form_submit_button("Apply", use_container_width=True)

df = _load_instances(d1, d2, created_by, q)
st.caption(f"{len(df)} instance(s)")

if df.empty:
    st.info("No cross instances in this range.")
    st.stop()

dfv = df[[
    "cross_run","cross_date","cross_code","cross_name","cross_name_genotype","clutch_code","date_birth","created_by","created_at"
]].copy()
dfv.insert(0,"✓ Select", False)

inst_edit = st.data_editor(
    dfv, hide_index=True, use_container_width=True, num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "cross_date": st.column_config.DateColumn("cross_date", disabled=True),
        "date_birth": st.column_config.DateColumn("date_birth", disabled=True),
        "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key="nursery_pick_editor",
)
sel_mask = inst_edit.get("✓ Select", pd.Series(False, index=inst_edit.index)).fillna(False).astype(bool)
picked = df.loc[sel_mask, :].reset_index(drop=True)

st.subheader("Set line-building stage")
st.caption("Choose a stage and apply to selected instance(s).")
stage = st.selectbox("line_building_stage", ["","zygote","2-cell","blastula","gastrula","segmentation","pharyngula","larval","juvenile","adult"], index=0)
note  = st.text_input("Note (optional)", "")

colA,colB = st.columns([1,1])
with colA:
    preview = pd.DataFrame([{"cross_run": r.cross_run, "clutch_code": r.clutch_code} for r in picked.itertuples(index=False)]) if not picked.empty else pd.DataFrame()
    st.dataframe(preview, use_container_width=True, hide_index=True, height=160)
with colB:
    st.write("")
    st.write("")

can_write = bool(stage.strip()) and not picked.empty
creator = os.environ.get("USER") or os.environ.get("USERNAME") or "system"

if st.button("💾 Apply stage to selected", type="primary", use_container_width=True, disabled=not can_write):
    updated, events = 0, 0
    has_inline = _col_exists("public","clutch_instances","line_building_stage")
    has_events = _table_exists("public","line_building_stage_events")
    with _eng().begin() as cx:
        for r in picked.itertuples(index=False):
            if has_inline:
                cx.execute(text("""
                    update public.cross_instances
                    set line_building_stage = :stg
                    where cross_run_code = :run
                """), {"stg": stage, "run": r.cross_run})
                updated += 1
            if has_events:
                cx.execute(text("""
                    insert into public.line_building_stage_events (cross_run_code, stage, observed_at, set_by, note)
                    values (:run, :stg, now(), :by, :note)
                """), {"run": r.cross_run, "stg": stage, "by": creator, "note": note})
                events += 1
    msg = f"Applied stage to {updated} instance(s)"
    if has_events: msg += f"; recorded {events} event row(s)"
    st.success(msg)
    st.rerun()