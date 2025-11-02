# =============================================================================
# 🐣 Annotate Clutch Instances — current contract (v_clutch_instances)
# =============================================================================
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
if not DB_URL:
    st.error("DB_URL not set")
    st.stop()
eng = get_engine()

VIEW = "public.v_clutch_instances"                # current view

# ---------- data ----------
def _load_clutches_filtered(d1: date, d2: date, who: str, q: str, most_recent: bool) -> pd.DataFrame:
    where, p = [], {}
    if not most_recent:
        where.append("v.created_at_instance::date BETWEEN :d1 AND :d2")
        p.update({"d1": d1, "d2": d2})
    if who.strip():
        where.append("COALESCE(v.created_by_instance,'') ILIKE :by")
        p["by"] = f"%{who.strip()}%"
    if q.strip():
        p["q"] = f"%{q.strip()}%"
        where.append("""(
          COALESCE(v.clutch_code,'')                         ILIKE :q OR
          COALESCE(v.cross_name_pretty,'')                   ILIKE :q OR
          COALESCE(v.clutch_name,'')                         ILIKE :q OR
          COALESCE(v.clutch_genotype_pretty,'')              ILIKE :q OR
          COALESCE(v.treatments_pretty_effective,'')         ILIKE :q OR
          COALESCE(v.genotype_treatment_rollup_effective,'') ILIKE :q
        )""")
    wsql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = text(f"""
      SELECT
        v.clutch_code,
        v.cross_name_pretty,
        v.clutch_name,
        v.clutch_genotype_pretty,
        v.genotype_treatment_rollup_effective,
        v.treatments_count_effective,
        v.treatments_pretty_effective,
        v.clutch_birthday,
        v.created_by_instance,
        v.created_at_instance
      FROM {VIEW} v
      {wsql}
      ORDER BY v.created_at_instance DESC NULLS LAST, v.clutch_code
      LIMIT 500
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=p)

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    if "treatments_count_effective" in df.columns:
        df["treatments_count_effective"] = (
            pd.to_numeric(df["treatments_count_effective"], errors="coerce")
              .fillna(0).astype(int)
        )
    return df

def _resolve_ci_id(code: str) -> Optional[str]:
    if not code:
        return None
    with eng.begin() as cx:
        df = pd.read_sql(text("""
            SELECT id::text AS clutch_instance_id
            FROM public.clutch_instances
            WHERE clutch_instance_code = :c
            LIMIT 1
        """), cx, params={"c": code})
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
    return None

def _load_ci_annotation(cid: str) -> pd.DataFrame:
    with eng.begin() as cx:
        sql = text("""
        WITH ci AS (
          SELECT id, clutch_instance_code, created_at
          FROM public.clutch_instances
          WHERE id = CAST(:cid AS uuid)
          LIMIT 1
        ),
        pvt AS (
          SELECT *
          FROM public.v_clutch_annotations_pivot
          WHERE clutch_code = (SELECT clutch_instance_code FROM ci)
          LIMIT 1
        ),
        latest AS (
          SELECT created_by, created_at
          FROM public.v_annotations_latest
          WHERE target_type='clutch'
            AND target_id = CAST(:cid AS uuid)
            AND kind_code IN ('red_intensity','green_intensity','notes','green_frequency','red_frequency','n_animals')
          ORDER BY created_at DESC
          LIMIT 1
        )
        SELECT
          ci.id::text                          AS clutch_instance_id,
          ci.clutch_instance_code,
          pvt.red_intensity,
          pvt.green_intensity,
          pvt.green_frequency,
          pvt.red_frequency,
          pvt.n_animals,
          pvt.notes,
          (pvt.red_intensity        IS NOT NULL) AS red_selected,
          (pvt.green_intensity      IS NOT NULL) AS green_selected,
          (pvt.green_frequency      IS NOT NULL) AS greenfreq_selected,
          (pvt.red_frequency        IS NOT NULL) AS redfreq_selected,
          (pvt.n_animals            IS NOT NULL) AS n_animals_selected,
          latest.created_by                       AS annotated_by,
          latest.created_at                       AS annotated_at,
          ci.created_at
        FROM ci
        LEFT JOIN pvt    ON TRUE
        LEFT JOIN latest ON TRUE
        """)
        return pd.read_sql(sql, cx, params={"cid": cid})

def _update_ci_annotation(cid: str, red: str, green: str, note: str, fallback_user: str,
                          gfreq: str = "", rfreq: str = "", n_animals: str = ""):
    who = (getattr(user, "email", "") or fallback_user or "")
    with eng.begin() as cx:
        if (red or "").strip() != "":
            cx.execute(text("""
              INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, created_by)
              SELECT 'clutch', CAST(:cid AS uuid), a.id, NULLIF(:v,'')::numeric,
                     COALESCE(current_setting('app.user', TRUE), :who)
              FROM public.annotations a
              WHERE a.kind_code='red_intensity'
            """), {"cid": cid, "v": red, "who": who})

        if (green or "").strip() != "":
            cx.execute(text("""
              INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, created_by)
              SELECT 'clutch', CAST(:cid AS uuid), a.id, NULLIF(:v,'')::numeric,
                     COALESCE(current_setting('app.user', TRUE), :who)
              FROM public.annotations a
              WHERE a.kind_code='green_intensity'
            """), {"cid": cid, "v": green, "who": who})

        if (gfreq or "").strip() != "":
            cx.execute(text("""
              INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, created_by)
              SELECT 'clutch', CAST(:cid AS uuid), a.id, NULLIF(:v,'')::numeric,
                     COALESCE(current_setting('app.user', TRUE), :who)
              FROM public.annotations a
              WHERE a.kind_code='green_frequency'
            """), {"cid": cid, "v": gfreq, "who": who})

        if (rfreq or "").strip() != "":
            cx.execute(text("""
              INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, created_by)
              SELECT 'clutch', CAST(:cid AS uuid), a.id, NULLIF(:v,'')::numeric,
                     COALESCE(current_setting('app.user', TRUE), :who)
              FROM public.annotations a
              WHERE a.kind_code='red_frequency'
            """), {"cid": cid, "v": rfreq, "who": who})

        if (n_animals or "").strip() != "":
            cx.execute(text("""
              INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, created_by)
              SELECT 'clutch', CAST(:cid AS uuid), a.id, NULLIF(:v,'')::numeric,
                     COALESCE(current_setting('app.user', TRUE), :who)
              FROM public.annotations a
              WHERE a.kind_code='n_animals'
            """), {"cid": cid, "v": n_animals, "who": who})

        if (note or "").strip() != "":
            cx.execute(text("""
              INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_text, created_by)
              SELECT 'clutch', CAST(:cid AS uuid), a.id, NULLIF(:v,''),
                     COALESCE(current_setting('app.user', TRUE), :who)
              FROM public.annotations a
              WHERE a.kind_code='notes'
            """), {"cid": cid, "v": note, "who": who})

# ---------- filters ----------
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: created_by = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt = st.text_input("Search (code/cross/clutch/genotype/strain)", value="")
    r1, r2 = st.columns([1, 3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", width="stretch")

df = _load_clutches_filtered(d1, d2, created_by, qtxt, ignore_dates)
st.caption(f"{len(df)} clutch(es)")
if df.empty:
    st.info("No clutches found with the current filters.")
    st.stop()

cols = [
    "clutch_code","cross_name_pretty","clutch_name",
    "clutch_genotype_pretty","genotype_treatment_rollup_effective",
    "treatments_count_effective","treatments_pretty_effective",
    "clutch_birthday","created_by_instance",
]
dfv = df[cols].copy()
dfv.insert(0, "✓ Select", False)
last_ci = st.session_state.get("__annot_last_ci")
if last_ci:
    dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv, hide_index=True, width="stretch", num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
    },
    column_order=["✓ Select"] + cols,
    key="annotate_ci_picker_v4",
)
sel = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False).astype(bool)
picked = dfv[sel].reset_index(drop=True)
if picked.empty:
    st.info("Select a clutch instance row to annotate it.")
    st.stop()

ci_code = str(picked.iloc[0]["clutch_code"])
st.session_state["__annot_last_ci"] = ci_code
cid = _resolve_ci_id(ci_code)
if not cid:
    st.error("Could not resolve clutch_instance_id from this code.")
    st.stop()

st.caption(f"{ci_code} — {picked.iloc[0]['genotype_treatment_rollup_effective']}")
st.subheader("Annotate this clutch instance")

cur = _load_ci_annotation(cid)
row = cur.iloc[0] if not cur.empty else {}

# inputs
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    red_val = st.number_input("red_intensity", min_value=0.0, max_value=1.0, step=0.05,
                              value=float(row.get("red_intensity") or 0.0))
with c2:
    green_val = st.number_input("green_intensity", min_value=0.0, max_value=1.0, step=0.05,
                                value=float(row.get("green_intensity") or 0.0))
with c3:
    note_txt = st.text_input("note", value=str(row.get("notes") or ""), placeholder="optional")

c4, c5, c6 = st.columns([1, 1, 1])
with c4:
    gfreq_val = st.number_input("green_frequency (0–1)", min_value=0.0, max_value=1.0, step=0.05,
                                value=float(row.get("green_frequency") or 0.0))
with c5:
    rfreq_val = st.number_input("red_frequency (0–1)", min_value=0.0, max_value=1.0, step=0.05,
                                value=float(row.get("red_frequency") or 0.0))
with c6:
    n_val = st.number_input("n_animals (integer ≥ 0)", min_value=0, step=1,
                            value=int(row.get("n_animals") or 0))

# save
if st.button("Save annotation", width="stretch", key="save_ci_annotation"):
    _update_ci_annotation(
        cid,
        "" if red_val   is None else str(red_val),
        "" if green_val is None else str(green_val),
        note_txt,
        fallback_user=(getattr(user, "email", "") or ""),
        gfreq="" if gfreq_val is None else str(gfreq_val),
        rfreq="" if rfreq_val is None else str(rfreq_val),
        n_animals="" if n_val is None else str(n_val),
    )
    st.success("Annotation saved.")

# display
st.subheader("Updated clutch instance")
updated = _load_ci_annotation(cid)
if updated.empty:
    st.info("No record found (unexpected).")
else:
    show_cols = [
        "clutch_instance_code",
        "red_intensity", "green_intensity",
        "green_frequency", "red_frequency", "n_animals",
        "notes",
        "red_selected", "green_selected", "greenfreq_selected", "redfreq_selected", "n_animals_selected",
        "annotated_by", "annotated_at", "created_at",
    ]
    st.dataframe(updated[[c for c in show_cols if c in updated.columns]], width="stretch", hide_index=True)