# carp_app/ui/pages/023_🧫_enter_bruker_mount.py
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
from typing import Optional
import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()
from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

st.set_page_config(page_title="🧫 Enter Mounts", page_icon="🧫", layout="wide")
st.title("🧫 Enter Mounts")

DB_URL = os.getenv("DB_URL")
if not DB_URL: st.error("DB_URL not set"); st.stop()
eng = get_engine()

MOUNT_ORIENTATION_OPTIONS = ["dorsal_head_top","lateral_head_right","lateral_head_left"]
MOUNT_ORIENTATION_DEFAULT = "dorsal_head_top"

def _load_clutches_filtered(d1: date, d2: date, who: str, q: str, most_recent: bool) -> pd.DataFrame:
    where, p = [], {}
    if not most_recent:
        where.append("created_at_instance::date BETWEEN :d1 AND :d2")
        p.update({"d1": d1, "d2": d2})
    if who.strip():
        where.append("COALESCE(created_by_instance,'') ILIKE :by")
        p["by"] = f"%{who.strip()}%"
    if q.strip():
        p["q"] = f"%{q.strip()}%"
        where.append("""(
          COALESCE(clutch_code,'') ILIKE :q OR
          COALESCE(cross_name_pretty,'') ILIKE :q OR
          COALESCE(clutch_name,'') ILIKE :q OR
          COALESCE(clutch_genotype_pretty,'') ILIKE :q OR
          COALESCE(treatments_pretty_effective,'') ILIKE :q OR
          COALESCE(genotype_treatment_rollup_effective,'') ILIKE :q OR
          COALESCE(mom_fish_code,'') ILIKE :q OR
          COALESCE(dad_fish_code,'') ILIKE :q
        )""")
    wsql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = text(f"""
      SELECT *
      FROM public.v_clutches_for_entry
      {wsql}
      ORDER BY created_at_instance DESC NULLS LAST, clutch_code
      LIMIT 500
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=p)
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    if "treatments_count_effective" in df.columns:
        df["treatments_count_effective"] = pd.to_numeric(df["treatments_count_effective"], errors="coerce").fillna(0).astype(int)
    return df

def _resolve_ci_id(code: str) -> Optional[str]:
    if not code: return None
    with eng.begin() as cx:
        df = pd.read_sql(text("""
            SELECT id::text AS clutch_instance_id
            FROM public.clutch_instances
            WHERE clutch_instance_code = :c
            LIMIT 1
        """), cx, params={"c": code})
        if not df.empty: return df["clutch_instance_id"].iloc[0]
        df = pd.read_sql(text("""
            SELECT id::text AS clutch_instance_id
            FROM public.clutch_instances
            WHERE upper(regexp_replace(COALESCE(clutch_instance_code,''), '-[0-9]{2}$','')) =
                  upper(regexp_replace(:c, '^CI-',''))
            LIMIT 1
        """), cx, params={"c": code})
        if not df.empty: return df["clutch_instance_id"].iloc[0]
        df = pd.read_sql(text("""
            SELECT ci.id::text AS clutch_instance_id
            FROM public.clutch_instances ci
            JOIN public.cross_instances x ON x.id = ci.cross_instance_id
            WHERE upper(regexp_replace(x.cross_run_code, '-[0-9]{2}$','')) =
                  upper(regexp_replace(:c, '^CI-',''))
            ORDER BY ci.created_at DESC NULLS LAST
            LIMIT 1
        """), cx, params={"c": code})
        if not df.empty: return df["clutch_instance_id"].iloc[0]
    return None

_PREVIEW_SQL = text("""
  WITH today AS (SELECT to_char((now() AT TIME ZONE 'UTC'),'YYYYMMDD') AS ymd),
  nextn AS (
    SELECT COALESCE(MAX( ((regexp_match(mount_code, '^MT-(\\d{8})-(\\d+)$'))[2])::int ), 0) + 1 AS n
    FROM public.mounts, today
    WHERE to_char(COALESCE(time_mounted, now()), 'YYYYMMDD') = (SELECT ymd FROM today)
      AND mount_code LIKE ('MT-'||(SELECT ymd FROM today)||'-%')
  )
  SELECT 'MT-'||(SELECT ymd FROM today)||'-'||(SELECT n FROM nextn) AS code
""")

_INSERT_SQL = text("""
  WITH today AS (SELECT to_char((now() AT TIME ZONE 'UTC'),'YYYYMMDD') AS ymd),
  nextn AS (
    SELECT COALESCE(MAX( ((regexp_match(mount_code, '^MT-(\\d{8})-(\\d+)$'))[2])::int ), 0) + 1 AS n
    FROM public.mounts, today
    WHERE to_char(COALESCE(time_mounted, now()), 'YYYYMMDD') = (SELECT ymd FROM today)
      AND mount_code LIKE ('MT-'||(SELECT ymd FROM today)||'-%')
  ),
  ins AS (
    INSERT INTO public.mounts (
      clutch_instance_id, mount_code, time_mounted, mounting_orientation, n_top, n_bottom, notes
    )
    VALUES (
      CAST(:cid AS uuid),
      'MT-'||(SELECT ymd FROM today)||'-'||(SELECT n FROM nextn),
      now(),
      :ori,
      :n_top,
      :n_bottom,
      NULLIF(:notes,'')
    )
    RETURNING clutch_instance_id, mount_code, mounting_orientation, n_top, n_bottom, time_mounted, notes
  )
  SELECT * FROM ins
""")

def _preview_next_mount_code() -> str:
    with eng.begin() as cx:
        df = pd.read_sql(_PREVIEW_SQL, cx)
        return df["code"].iloc[0] if not df.empty else ""

def _insert_mount(cid: str, ori: str, n_top: int, n_bottom: int, notes: str) -> pd.DataFrame:
    with eng.begin() as cx:
        return pd.read_sql(_INSERT_SQL, cx, params={
            "cid": cid, "ori": ori, "n_top": int(n_top or 0), "n_bottom": int(n_bottom or 0), "notes": notes or "",
        })

def _load_latest_mount(cid: str) -> pd.DataFrame:
    with eng.begin() as cx:
        return pd.read_sql(text("""
          SELECT mount_code, mounting_orientation, n_top, n_bottom, time_mounted, notes
          FROM public.mounts
          WHERE clutch_instance_id = CAST(:cid AS uuid)
          ORDER BY time_mounted DESC
          LIMIT 1
        """), cx, params={"cid": cid})

# ---------- filters ----------
with st.form("enter_mounts_filters", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: who  = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt = st.text_input("Search (code/cross/genotype/parents)", value="")
    r1, r2 = st.columns([1,3])
    with r1: most_recent = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", width="stretch")

df = _load_clutches_filtered(d1, d2, who, qtxt, most_recent)
st.caption(f"{len(df)} clutch(es)")
if df.empty: st.info("No clutches found with the current filters."); st.stop()

cols = [
    "clutch_code","cross_name_pretty","clutch_name",
    "clutch_genotype_pretty","genotype_treatment_rollup_effective",
    "treatments_count_effective","treatments_pretty_effective",
    "clutch_birthday","created_by_instance",
]
dfv = df[cols].copy()
dfv.insert(0, "✓ Select", False)
last_ci = st.session_state.get("__enter_mounts_last_ci")
if last_ci: dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv, hide_index=True, width="stretch", num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True),
    },
    column_order=["✓ Select"] + cols,
    key="enter_mounts_ci_picker_v6",
)
sel = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False)
picked = dfv[sel].reset_index(drop=True)
if picked.empty: st.info("Select a clutch instance row to enter its mount."); st.stop()

ci_code = str(picked.iloc[0]["clutch_code"])
st.session_state["__enter_mounts_last_ci"] = ci_code
cid = _resolve_ci_id(ci_code)
if not cid: st.error("Could not resolve clutch_instance_id from this code."); st.stop()

st.subheader("Enter mount for this clutch instance")
try:
    default_idx = MOUNT_ORIENTATION_OPTIONS.index(MOUNT_ORIENTATION_DEFAULT)
except ValueError:
    default_idx = 0
ori = st.selectbox("mount orientation", options=MOUNT_ORIENTATION_OPTIONS, index=default_idx)
notes_in = st.text_input("notes", value="")

_preview = st.empty()
def _refresh_preview():
    _preview.caption(f"Next auto code (preview): **{_preview_next_mount_code() or 'MT-YYYYMMDD-1'}**")
_refresh_preview()

c1,c2 = st.columns(2)
with c1: n_top = st.number_input("n_top", min_value=0, step=1, value=0)
with c2: n_bottom = st.number_input("n_bottom", min_value=0, step=1, value=0)

nonce = st.session_state.get("__enter_mounts_nonce", 0)
msg = st.session_state.pop("__enter_mounts_msg", None)
if msg: st.success(msg)

if st.button("Save mount", width="stretch", key=f"save_mount_btn_{nonce}"):
    saved = _insert_mount(cid, ori, n_top, n_bottom, notes_in)
    code = saved.iloc[0]["mount_code"] if not saved.empty else ""
    st.session_state["__enter_mounts_msg"] = f"Mount saved as **{code or '(created)'}**."
    st.session_state["__enter_mounts_nonce"] = nonce + 1
    st.rerun()

st.subheader("Updated mount (latest)")
latest = _load_latest_mount(cid)
if latest.empty:
    st.info("No mount rows yet for this clutch instance.")
else:
    st.dataframe(latest, width="stretch", hide_index=True)