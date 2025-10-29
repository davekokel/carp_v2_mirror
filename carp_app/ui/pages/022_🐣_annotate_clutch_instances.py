# carp_app/ui/pages/020_🧪_annotate_clutch_instances.py
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

st.set_page_config(page_title="🐣 Annotate Clutch Instances", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Clutch Instances")

DB_URL = os.getenv("DB_URL")
if not DB_URL: st.error("DB_URL not set"); st.stop()
eng = get_engine()

# ---------- data ----------
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

def _load_ci_annotation(cid: str) -> pd.DataFrame:
    with eng.begin() as cx:
        return pd.read_sql(text("""
          SELECT id::text AS clutch_instance_id, clutch_instance_code, label,
                 red_intensity, green_intensity, notes,
                 red_selected, green_selected, annotated_by, annotated_at, created_at
          FROM public.clutch_instances
          WHERE id = CAST(:cid AS uuid)
          LIMIT 1
        """), cx, params={"cid": cid})

def _update_ci_annotation(cid: str, red: str, green: str, note: str, fallback_user: str):
    with eng.begin() as cx:
        cx.execute(text("""
          UPDATE public.clutch_instances
          SET red_intensity   = NULLIF(:r,''),
              green_intensity = NULLIF(:g,''),
              notes           = NULLIF(:n,''),
              red_selected    = (NULLIF(:r,'') IS NOT NULL),
              green_selected  = (NULLIF(:g,'') IS NOT NULL),
              annotated_by    = COALESCE(current_setting('app.user', TRUE), :who),
              annotated_at    = now()
          WHERE id = CAST(:cid AS uuid)
        """), {"cid": cid, "r": red, "g": green, "n": note, "who": (getattr(user, "email", "") or fallback_user or "")})

# ---------- filters ----------
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: created_by = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt = st.text_input("Search (code/cross/clutch/genotype/strain/mom/dad)", value="")
    r1, r2 = st.columns([1,3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", width="stretch")

df = _load_clutches_filtered(d1, d2, created_by, qtxt, ignore_dates)
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
last_ci = st.session_state.get("__annot_last_ci")
if last_ci: dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv, hide_index=True, use_container_width=True, num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True),
    },
    column_order=["✓ Select"] + cols,
    key="annotate_ci_picker_v3",
)
sel = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False)
picked = dfv[sel].reset_index(drop=True)
if picked.empty: st.info("Select a clutch instance row to annotate it."); st.stop()

ci_code = str(picked.iloc[0]["clutch_code"])
st.session_state["__annot_last_ci"] = ci_code
cid = _resolve_ci_id(ci_code)
if not cid: st.error("Could not resolve clutch_instance_id from this code."); st.stop()

st.caption(f"{ci_code} — {picked.iloc[0]['genotype_treatment_rollup_effective']}")
st.subheader("Annotate this clutch instance")

cur = _load_ci_annotation(cid)
row = cur.iloc[0] if not cur.empty else {}
c1,c2,c3 = st.columns([1,1,2])
with c1: red_txt = st.text_input("red", value=str(row.get("red_intensity") or ""))
with c2: green_txt = st.text_input("green", value=str(row.get("green_intensity") or ""))
with c3: note_txt = st.text_input("note", value=str(row.get("notes") or ""), placeholder="optional")

if st.button("Save annotation", width="stretch", key="save_ci_annotation"):
    _update_ci_annotation(cid, red_txt, green_txt, note_txt, fallback_user=(getattr(user,"email","") or ""))
    st.success("Annotation saved.")

st.subheader("Updated clutch instance")
updated = _load_ci_annotation(cid)
if updated.empty:
    st.info("No record found (unexpected).")
else:
    show_cols = ["clutch_instance_code","label","red_intensity","green_intensity","notes",
                 "red_selected","green_selected","annotated_by","annotated_at","created_at"]
    st.dataframe(updated[[c for c in show_cols if c in updated.columns]], width="stretch", hide_index=True)