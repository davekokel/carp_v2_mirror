from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

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
def _view_exists(schema: str, name: str) -> bool:
    with eng.begin() as cx:
        q = text("select 1 from information_schema.views where table_schema=:s and table_name=:t limit 1")
        return bool(pd.read_sql(q, cx, params={"s": schema, "t": name}).shape[0])

def _table_exists(schema: str, name: str) -> bool:
    with eng.begin() as cx:
        q = text("select 1 from information_schema.tables where table_schema=:s and table_name=:t limit 1")
        return bool(pd.read_sql(q, cx, params={"s": schema, "t": name}).shape[0])

def _load_instances(d1: date, d2: date, created_by: str, q: str, ignore_dates: bool) -> pd.DataFrame:
    if not _view_exists("public","v_clutches_overview_final"):
        st.error("Missing view public.v_clutches_overview_final."); st.stop()

    where_bits, params = [], {}
    if not ignore_dates:
        where_bits.append("coalesce(clutch_birthday, date_planned) between :d1 and :d2")
        params["d1"], params["d2"] = d1, d2
    if (created_by or "").strip():
        where_bits.append("(created_by_instance ilike :byl or created_by_plan ilike :byl)")
        params["byl"] = f"%{created_by.strip()}%"
    if (q or "").strip():
        where_bits.append("""(
          coalesce(clutch_code,'') ilike :ql or
          coalesce(cross_name_pretty,'') ilike :ql or
          coalesce(clutch_name,'') ilike :ql or
          coalesce(clutch_genotype_pretty,'') ilike :ql or
          coalesce(treatments_pretty,'') ilike :ql or
          coalesce(annotation_rollup,'') ilike :ql or
          coalesce(mom_strain,'') ilike :ql or coalesce(dad_strain,'') ilike :ql
        )""")
        params["ql"] = f"%{q.strip()}%"
    where_sql = " AND ".join(where_bits) if where_bits else "true"

    sql = text(f"""
      select *
      from public.v_clutches_overview_final
      where {where_sql}
      order by created_at_instance desc nulls last, clutch_birthday desc nulls last
      limit 500
    """)
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params=params)

def _load_recent_bruker_mounts(limit: int = 200) -> pd.DataFrame:
    if not _table_exists("public","bruker_mount"):
        return pd.DataFrame()
    with eng.begin() as cx:
        return pd.read_sql(text("""
          select
            mount_code,
            mount_date,
            mount_time,
            mount_orientation,
            mount_top_n,
            mount_bottom_n,
            mount_notes,
            -- optional: a computed timestamp for display/sorting
            (mount_date::timestamp + coalesce(mount_time, time '00:00')) as mount_ts
          from public.bruker_mount
          order by (mount_date::timestamp + coalesce(mount_time, time '00:00')) desc nulls last
          limit :lim
        """), cx, params={"lim": int(limit)})

# ───────────────────────── top filter bar ─────────────────────────
st.caption(
    f"DB: {(getattr(getattr(eng, 'url', None), 'host', None) or os.getenv('PGHOST', '(unknown)'))}"
    f" • role={getattr(user, 'role', None) or 'none'}"
    f" • user={getattr(user, 'email', None) or 'postgres'}"
)

with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: created_by = st.text_input("Created by (plan/instance)", value="")
    with c4: q = st.text_input("Search (code/cross/clutch/genotype/strain/annotation)", value="")
    r1, r2 = st.columns([1,3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", use_container_width=True)

# ───────────────────────── 1) Choose clutch instance (from v_clutches_overview_final) ─────────────────────────
instances = _load_instances(d1, d2, created_by, q, ignore_dates)
st.header("1) Choose clutch instance")
st.caption(f"{len(instances)} clutch instance(s)")

if instances.empty:
    st.info("No instances match the current filters."); st.stop()

grid = instances.copy()
if "✓" not in grid.columns:
    grid.insert(0, "✓", False)

view_cols = [
    "✓",
    "clutch_code","clutch_birthday","cross_name_pretty",
    "genotype_treatment_rollup",
    "clutch_genotype_pretty","clutch_genotype_canonical",
    "mom_strain","dad_strain","clutch_strain_pretty",
    "treatments_count","treatments_pretty",
    "annotations_count","annotation_rollup",
    "created_by_instance","created_at_instance",
]
present = [c for c in view_cols if c in grid.columns]

edited_instances = st.data_editor(
    grid[present],
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=present,
    column_config={
        "✓": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True),
        "created_at_instance": st.column_config.DatetimeColumn("created_at_instance", disabled=True),
        "genotype_treatment_rollup": st.column_config.TextColumn(
            "genotype_treatment_rollup", help="treatments_pretty > clutch_genotype_pretty"
        ),
        "annotations_count": st.column_config.NumberColumn("# annotations", help="Count of selection rows"),
        "annotation_rollup": st.column_config.TextColumn(
            "annotation_rollup", help="Latest selection: red/green intensities and note"
        ),
    },
    key="bruker_instances_editor",
)
grid.loc[edited_instances.index, "✓"] = edited_instances["✓"]

picked = grid.loc[grid["✓"] == True].reset_index(drop=True)
if picked.empty:
    st.info("Tick exactly one clutch instance to continue."); st.stop()
if len(picked) > 1:
    st.warning("Tick exactly **one** clutch instance to continue."); st.stop()

clutch_row = picked.iloc[0]
clutch_id  = str(clutch_row.get("clutch_id","") or "")
if not clutch_id:
    st.error("Selected row is missing clutch_id; please refresh."); st.stop()

st.caption(
    "Selected: "
    f"{clutch_row.get('clutch_code','')} • "
    f"{clutch_row.get('cross_name_pretty','')} • "
    f"geno: {clutch_row.get('clutch_genotype_pretty','')} • "
    f"treat: {clutch_row.get('treatments_pretty','')} • "
    f"anno: {clutch_row.get('annotation_rollup','')}"
)

# ───────────────────────── 2) Enter Bruker mount (exact fields) ─────────────────────────
st.header("2) Enter Bruker mount")

if not _table_exists("public","bruker_mount"):
    st.error("Table public.bruker_mount not found.")
    st.caption("Expected columns: mount_code, mount_date, mount_time, mount_orientation, mount_top_n, mount_bottom_n, mount_notes")
    st.stop()

m1, m2 = st.columns([2,1])
with m1:
    mount_code = st.text_input("mount_code", value="", placeholder="e.g., MT-2025-10-18-01")
with m2:
    mount_orientation = st.selectbox("mount_orientation", ["dorsal_up","ventral_up","lateral_left","lateral_right","other"])

m3, m4, m5 = st.columns([1,1,2])
with m3:
    mount_date = st.date_input("mount_date", value=date.today())
with m4:
    mount_time = st.time_input("mount_time (optional)", value=time(0, 0))
with m5:
    mount_notes = st.text_input("mount_notes", value="", placeholder="optional")

m6, m7 = st.columns([1,1])
with m6:
    mount_top_n = st.number_input("mount_top_n", min_value=0, value=0, step=1)
with m7:
    mount_bottom_n = st.number_input("mount_bottom_n", min_value=0, value=0, step=1)

can_save = bool(mount_code.strip() and mount_date)
save_btn = st.button("Save mount", type="primary", use_container_width=True, disabled=not can_save)

if save_btn:
    # Compose timestamptz if you ever add a timestamptz column; for now we only send date + time textually
    with eng.begin() as cx:
        cx.execute(
            text("""
              insert into public.bruker_mount (
                mount_code, mount_date, mount_time,
                mount_orientation, mount_top_n, mount_bottom_n, mount_notes
              )
              values (
                :mount_code, :mount_date, :mount_time,
                :mount_orientation, :mount_top_n, :mount_bottom_n, :mount_notes
              )
            """),
            {
                "mount_code": mount_code.strip(),
                "mount_date": mount_date,
                "mount_time": mount_time,  # stored as time type if the table is time; else text is acceptable
                "mount_orientation": mount_orientation,
                "mount_top_n": int(mount_top_n or 0),
                "mount_bottom_n": int(mount_bottom_n or 0),
                "mount_notes": mount_notes.strip(),
            }
        )
    st.success(f"✅ Bruker mount saved: {mount_code}")
    st.rerun()

# ───────────────────────── 3) Existing Bruker mounts (latest) ─────────────────────────
st.subheader("Existing Bruker mounts (latest)")
bm = _load_recent_bruker_mounts(limit=200)
if bm.empty:
    st.caption("No Bruker mounts recorded yet.")
else:
    cols = [
        "mount_code",
        "mount_date","mount_time","mount_orientation",
        "mount_top_n","mount_bottom_n","mount_notes",
    ]
    st.dataframe(bm[[c for c in cols if c in bm.columns]],
                 hide_index=True, use_container_width=True)