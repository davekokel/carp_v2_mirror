from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, List

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

st.set_page_config(page_title="🧫 Enter Mounts", page_icon="🧫", layout="wide")
st.title("🧫 Enter Mounts")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

MOUNT_ORIENTATION_OPTIONS = [
    "Lateral, Heart Down, Head front",
    "Lateral, Heart Up, Head front",
    "Lateral, Heart Up, Tail front",
    "Lateral, Heart Down, Tail front",
    "Vertical, Tail Up, Heart at DO",
    "Vertical, Tail Up, Heart at EO",
    "Vertical, Head Up, Heart at DO",
    "Vertical, Head Up, Heart at EO",
    "Dorsal, Head user",
    "Dorsal, Tail user",
    "Ventral, Tail user",
    "Ventral, Head user",
]
MOUNT_ORIENTATION_DEFAULT = "Dorsal, Head user"

# ───────────────────────── utils ─────────────────────────
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

def _load_clutches_filtered(d1: date, d2: date, created_by: str, qtxt: str, ignore_dates: bool) -> pd.DataFrame:
    view = "public.v_clutches"
    if not _exists(view):
        st.error(f"Required view {view} not found."); st.stop()

    where_bits, params = [], {}
    if not ignore_dates:
        where_bits.append("created_at::date between :d1 and :d2")
        params["d1"], params["d2"] = d1, d2
    if (created_by or "").strip():
        where_bits.append("coalesce(created_by,'') ilike :byl")
        params["byl"] = f"%{created_by.strip()}%"
    if (qtxt or "").strip():
        where_bits.append("""(
          coalesce(clutch_code,'') ilike :ql or
          coalesce(name,'')        ilike :ql or
          coalesce(nickname,'')    ilike :ql or
          coalesce(mom_code,'')    ilike :ql or
          coalesce(dad_code,'')    ilike :ql
        )""")
        params["ql"] = f"%{qtxt.strip()}%"
    where_sql = " AND ".join(where_bits) if where_bits else "true"

    sql = text(f"""
      select
        clutch_code,
        name     as clutch_name,
        nickname as clutch_nickname,
        mom_code,
        dad_code,
        created_by as created_by_instance,
        created_at as created_at_instance
      from {view}
      where {where_sql}
      order by created_at desc nulls last, clutch_code
      limit 500
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # Provide columns this page references but v_clutches doesn’t expose
    for missing in [
        "cross_name_pretty",
        "clutch_genotype_pretty",
        "genotype_treatment_rollup_effective",
        "treatments_count_effective",
        "treatments_pretty_effective",
        "clutch_birthday",
    ]:
        if missing not in df.columns:
            df[missing] = pd.NA

    if "treatments_count_effective" in df.columns:
        df["treatments_count_effective"] = pd.to_numeric(df["treatments_count_effective"], errors="coerce").fillna(0).astype(int)

    df = df.loc[:, ~df.columns.duplicated()]
    return df

def _resolve_ci_id(ci_code: str) -> Optional[str]:
    if not ci_code or not isinstance(ci_code, str):
        return None
    with eng.begin() as cx:
        df = pd.read_sql(text("""
            select id::text as clutch_instance_id
            from public.clutch_instances
            where clutch_instance_code = :ci
            limit 1
        """), cx, params={"ci": ci_code})
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
        df = pd.read_sql(text("""
            select id::text as clutch_instance_id
            from public.clutch_instances
            where upper(regexp_replace(coalesce(clutch_instance_code,''), '-[0-9]{2}$','')) =
                  upper(regexp_replace(:ci, '^CI-',''))
            limit 1
        """), cx, params={"ci": ci_code})
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
        df = pd.read_sql(text("""
            select ci.id::text as clutch_instance_id
            from public.clutch_instances ci
            join public.cross_instances x on x.id = ci.cross_instance_id
            where upper(regexp_replace(x.cross_run_code, '-[0-9]{2}$','')) =
                  upper(regexp_replace(:ci, '^CI-',''))
            order by ci.created_at desc nulls last
            limit 1
        """), cx, params={"ci": ci_code})
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
    return None

# ─────────── Auto mount_code (MT-YYYYMMDD-n) helpers — UTC day ───────────
_PREVIEW_SQL = text("""
  with today as (select to_char((now() at time zone 'UTC'),'YYYYMMDD') as ymd),
  nextn as (
    select coalesce(max( ((regexp_match(mount_code, '^MT-(\\d{8})-(\\d+)$'))[2])::int ), 0) + 1 as n
    from public.bruker_mount, today
    where to_char(coalesce(time_mounted, now()), 'YYYYMMDD') = (select ymd from today)
      and mount_code like ('MT-'||(select ymd from today)||'-%')
  )
  select 'MT-'||(select ymd from today)||'-'||(select n from nextn) as code
""")

_INSERT_SQL = text("""
  with today as (select to_char((now() at time zone 'UTC'),'YYYYMMDD') as ymd),
  nextn as (
    select coalesce(max( ((regexp_match(mount_code, '^MT-(\\d{8})-(\\d+)$'))[2])::int ), 0) + 1 as n
    from public.bruker_mount, today
    where to_char(coalesce(time_mounted, now()), 'YYYYMMDD') = (select ymd from today)
      and mount_code like ('MT-'||(select ymd from today)||'-%')
  ),
  ins as (
    insert into public.bruker_mount (
      clutch_instance_id, mount_code, time_mounted, mounting_orientation, n_top, n_bottom
    )
    values (
      cast(:cid as uuid),
      'MT-'||(select ymd from today)||'-'||(select n from nextn),
      now(),
      :ori,
      :n_top,
      :n_bottom
    )
    returning clutch_instance_id, mount_code, mounting_orientation, n_top, n_bottom, time_mounted
  )
  select * from ins
""")

def _preview_next_mount_code() -> str:
    with eng.begin() as cx:
        df = pd.read_sql(_PREVIEW_SQL, cx)
        return df["code"].iloc[0] if not df.empty else ""

def _insert_bruker_mount_auto_code(cid: str, mounting_orientation: str, n_top: int, n_bottom: int) -> pd.DataFrame:
    with eng.begin() as cx:
        return pd.read_sql(_INSERT_SQL, cx, params={
            "cid": cid,
            "ori": mounting_orientation,
            "n_top": int(n_top or 0),
            "n_bottom": int(n_bottom or 0),
        })

def _load_latest_bruker_mount(cid: str) -> pd.DataFrame:
    sql = text("""
      select
        bm.clutch_instance_id,
        bm.mount_code,
        bm.time_mounted,
        bm.mounting_orientation,
        bm.n_top,
        bm.n_bottom
      from public.bruker_mount bm
      where bm.clutch_instance_id = cast(:cid as uuid)
      order by bm.time_mounted desc
      limit 1
    """)
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params={"cid": cid})

# ─────────── Filters ───────────
with st.form("enter_mounts_filters", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: created_by = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt = st.text_input("Search (code/cross/clutch/genotype/strain)", value="")
    r1, r2 = st.columns([1,3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", use_container_width=True)

# ─────────── Pick CI ───────────
clutches = _load_clutches_filtered(d1, d2, created_by, qtxt, ignore_dates)
st.caption(f"{len(clutches)} clutch(es)")

if clutches.empty:
    st.info("No clutches found with the current filters."); st.stop()

view_cols = [
    "clutch_code","cross_name_pretty","clutch_name",
    "clutch_genotype_pretty","genotype_treatment_rollup_effective",
    "treatments_count_effective","treatments_pretty_effective",
    "clutch_birthday","created_by_instance",
]
have = [c for c in view_cols if c in clutches.columns]
dfv = clutches[have].copy()
dfv = dfv.loc[:, ~dfv.columns.duplicated()]
if "treatments_count_effective" in dfv.columns:
    dfv["treatments_count_effective"] = pd.to_numeric(dfv["treatments_count_effective"], errors="coerce").fillna(0).astype(int)

last_ci = st.session_state.get("__enter_mounts_last_ci")
dfv.insert(0, "✓ Select", False)
if last_ci and "clutch_code" in dfv.columns:
    dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True),
    },
    key="enter_mounts_ci_picker_v4",
)
sel_mask = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False).astype(bool)
picked = dfv.loc[sel_mask, :].reset_index(drop=True)

if picked.empty:
    st.info("Select a **CI-…** row to enter its mount.")
    st.stop()

ci_code = str(picked.iloc[0].get("clutch_code","")).strip()
st.session_state["__enter_mounts_last_ci"] = ci_code

if not ci_code.startswith("CI-"):
    st.warning("Pick a **CI-…** row (runs only). Plan rows (CL-…) don’t have a mount here."); st.stop()

cid = _resolve_ci_id(ci_code)
if not cid:
    st.error("Could not resolve clutch_instance_id from this CI code."); st.stop()

# ─────────── Enter mount ───────────
st.subheader("Enter mount for this clutch instance")

try:
    default_idx = MOUNT_ORIENTATION_OPTIONS.index(MOUNT_ORIENTATION_DEFAULT)
except ValueError:
    default_idx = 0

mount_orient = st.selectbox("mount orientation", options=MOUNT_ORIENTATION_OPTIONS, index=default_idx)

_preview_box = st.empty()
def _refresh_preview():
    p = _preview_next_mount_code()  # uses UTC day
    _preview_box.caption(f"Next auto code (preview): **{p or 'MT-YYYYMMDD-1'}**")
_refresh_preview()

col_nt, col_nb = st.columns(2)
with col_nt:
    n_top_in = st.number_input("n_top", min_value=0, step=1, value=0)
with col_nb:
    n_bottom_in = st.number_input("n_bottom", min_value=0, step=1, value=0)

nonce = st.session_state.get("__enter_mounts_nonce", 0)
msg = st.session_state.pop("__enter_mounts_msg", None)
if msg:
    st.success(msg)

if st.button("Save mount", use_container_width=True, key=f"save_mount_btn_{nonce}"):
    saved = _insert_bruker_mount_auto_code(
        cid=cid,
        mounting_orientation=mount_orient,
        n_top=n_top_in,
        n_bottom=n_bottom_in,
    )
    mc = saved.iloc[0]["mount_code"] if not saved.empty else ""
    st.session_state["__enter_mounts_msg"] = f"Mount saved as **{mc or '(created)'}**."
    st.session_state["__enter_mounts_nonce"] = nonce + 1
    st.rerun()

# ─────────── Latest & Recent ───────────
st.subheader("Updated mount (latest)")
latest = _load_latest_bruker_mount(cid)
if latest.empty:
    st.info("No mount rows yet for this clutch instance.")
else:
    cols = ["mount_code","mounting_orientation","n_top","n_bottom","time_mounted"]
    present = [c for c in cols if c in latest.columns]
    st.dataframe(latest[present], use_container_width=True, hide_index=True)

st.subheader("Recent mounts for this clutch instance")
sql_recent = text("""
  select
    bm.mount_code,
    bm.mounting_orientation,
    bm.n_top,
    bm.n_bottom,
    bm.time_mounted
  from public.bruker_mount bm
  where bm.clutch_instance_id = cast(:cid as uuid)
  order by bm.time_mounted desc
  limit 5
""")
with eng.begin() as cx:
    recent = pd.read_sql(sql_recent, cx, params={"cid": cid})

if recent.empty:
    st.info("No previous mounts yet.")
else:
    st.dataframe(recent, use_container_width=True, hide_index=True)
    last = recent.iloc[0]
    if st.button("Duplicate last mount", use_container_width=True, key=f"duplicate_mount_btn_{nonce}"):
        saved = _insert_bruker_mount_auto_code(
            cid=cid,
            mounting_orientation=str(last["mounting_orientation"]),
            n_top=int(last["n_top"]),
            n_bottom=int(last["n_bottom"]),
        )
        mc = saved.iloc[0]["mount_code"] if not saved.empty else ""
        st.session_state["__enter_mounts_msg"] = f"Duplicated last mount → **{mc}**"
        st.session_state["__enter_mounts_nonce"] = nonce + 1
        st.rerun()