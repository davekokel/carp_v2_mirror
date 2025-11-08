# =============================================================================
# 🐣 Annotate Treated Clutch Groups — lead with treated_clutch_code (v_treated_clutches)
#   • Picker lists baseline T(<CI>)-0 and all treated groups
#   • Reads current values from v_treated_clutch_annotations_pivot
#   • Writes annotations to join_annotations with target_type='treated_clutch'
#   • Intensities / frequencies use 1–100 scale
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

st.set_page_config(page_title="🐣 Annotate Treated Clutch Groups", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Treated Clutch Groups")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

# Views / tables
V_TCLUTCH = "public.v_treated_clutches"                 # groups (baseline + treated)
V_PVT_G   = "public.v_treated_clutch_annotations_pivot" # per-group pivot
V_LATEST  = "public.v_annotations_latest_group"         # per-group latest rows
T_CLUTCH  = "public.clutch_instances"                   # clutch context
T_JANN    = "public.join_annotations"                   # writes
T_ANN     = "public.annotations"                        # kinds

# ---------- helpers ----------
def _exists_view(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    sql = text("""
      SELECT 1
      FROM information_schema.views
      WHERE table_schema=:s AND table_name=:n
      UNION ALL
      SELECT 1
      FROM pg_catalog.pg_matviews
      WHERE schemaname=:s AND matviewname=:n
      LIMIT 1
    """)
    with eng.begin() as cx:
        return cx.execute(sql, {"s": sch, "n": name}).first() is not None

def _load_groups_filtered(d1: date, d2: date, q: str, most_recent: bool) -> pd.DataFrame:
    if not _exists_view(V_TCLUTCH):
        st.error(f"Required view not found: {V_TCLUTCH}"); st.stop()
    where, p = [], {}
    if not most_recent:
        where.append("vt.group_created_at::date BETWEEN :d1 AND :d2")
        p.update({"d1": d1, "d2": d2})
    if q.strip():
        p["q"] = f"%{q.strip()}%"
        where.append("""(
          vt.treated_clutch_code ILIKE :q OR
          vt.clutch_code         ILIKE :q OR
          vt.cross_name_pretty   ILIKE :q OR
          COALESCE(vt.clutch_genotype_pretty,'')   ILIKE :q OR
          COALESCE(vt.treatments_codes_group,'')   ILIKE :q OR
          COALESCE(vt.treatments_names_group,'')   ILIKE :q OR
          COALESCE(vt.treatment_genotype_group,'') ILIKE :q
        )""")
    wsql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = text(f"""
      SELECT
        vt.treated_clutch_code,
        vt.group_created_at,
        vt.treatments_count_group::int AS treatments_count_group,
        vt.treatments_codes_group,
        vt.treatments_names_group,
        vt.treatment_genotype_group,
        vt.clutch_code,
        vt.clutch_birthday,
        vt.cross_name_pretty,
        vt.clutch_genotype_pretty
      FROM {V_TCLUTCH} vt
      {wsql}
      ORDER BY
        vt.clutch_code,
        (regexp_match(vt.treated_clutch_code, '\\-(\\d+)$'))[1]::int ASC,
        vt.group_created_at ASC
      LIMIT 500
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=p)
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _resolve_ids_from_group(treated_clutch_code: str) -> tuple[Optional[str], Optional[str]]:
    if not treated_clutch_code: return None, None
    sql = text("""
      SELECT tc.id::text AS treated_clutch_id, ci.id::text AS clutch_instance_id
      FROM public.treated_clutches tc
      JOIN public.clutch_instances ci ON ci.id = tc.clutch_instance_id
      WHERE tc.treated_clutch_code = :g
      LIMIT 1
    """)
    with eng.begin() as cx:
        row = pd.read_sql(sql, cx, params={"g": treated_clutch_code})
    if row.empty: return None, None
    return row.iloc[0]["treated_clutch_id"], row.iloc[0]["clutch_instance_id"]

def _load_group_annotation(group_code: str) -> pd.DataFrame:
    if not _exists_view(V_PVT_G):
        return pd.DataFrame()
    sql = text(f"""
      SELECT *
      FROM {V_PVT_G}
      WHERE treated_clutch_code = :g
      LIMIT 1
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params={"g": group_code})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _update_group_annotation(treated_clutch_id: str, red: str, green: str, note: str, fallback_user: str,
                             gfreq: str = "", rfreq: str = "", n_animals: str = ""):
    who = (getattr(user, "email", "") or fallback_user or "")
    with eng.begin() as cx:
        def ins(kind:str, val:str, numeric=True):
            if (val or "").strip()=="":
                return
            if numeric:
                cx.execute(text(f"""
                  INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, created_by)
                  SELECT 'treated_clutch', CAST(:tid AS uuid), a.id, NULLIF(:v,'')::numeric,
                         COALESCE(current_setting('app.user', TRUE), :who)
                  FROM {T_ANN} a WHERE a.kind_code=:k
                """), {"tid": treated_clutch_id, "v": val, "k": kind, "who": who})
            else:
                cx.execute(text(f"""
                  INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_text, created_by)
                  SELECT 'treated_clutch', CAST(:tid AS uuid), a.id, NULLIF(:v,''), 
                         COALESCE(current_setting('app.user', TRUE), :who)
                  FROM {T_ANN} a WHERE a.kind_code=:k
                """), {"tid": treated_clutch_id, "v": val, "k": kind, "who": who})

        ins('red_intensity',   red)
        ins('green_intensity', green)
        ins('green_frequency', gfreq)
        ins('red_frequency',   rfreq)
        ins('n_animals',       n_animals)
        ins('notes',           note, numeric=False)

# ---------- filters ----------
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: qtxt = st.text_input("Search (group/clutch/cross/genotype/treatments)", value="")
    with c4: st.empty()
    r1, r2 = st.columns([1, 3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", width="stretch")

df = _load_groups_filtered(d1, d2, qtxt, ignore_dates)
st.caption(f"{len(df)} treated clutch group(s)")
if df.empty:
    st.info("No groups found with the current filters."); st.stop()

# lead with treated_clutch_code
cols = [
    "treated_clutch_code","group_created_at",
    "treatments_count_group","treatments_codes_group","treatments_names_group",
    "treatment_genotype_group",
    "clutch_code","clutch_birthday","cross_name_pretty","clutch_genotype_pretty",
]
dfv = df[cols].copy()
dfv.insert(0, "✓ Select", False)
last_group = st.session_state.get("__annot_last_group")
if last_group:
    dfv.loc[dfv["treated_clutch_code"] == last_group, "✓ Select"] = True

picker = st.data_editor(
    dfv, hide_index=True, width="stretch", num_rows="fixed",
    column_config={
        "✓ Select":               st.column_config.CheckboxColumn("✓", default=False),
        "group_created_at":       st.column_config.DatetimeColumn("created_at", disabled=True),
        "clutch_birthday":        st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
        "treatments_count_group": st.column_config.NumberColumn("# tx", format="%d", step=1, disabled=True),
    },
    column_order=["✓ Select"] + cols,
    key="annotate_group_picker_v1",
)
sel = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False).astype(bool)
picked = dfv[sel].reset_index(drop=True)
if picked.empty:
    st.info("Select a treated clutch group to annotate it.")
    st.stop()

group_code = str(picked.iloc[0]["treated_clutch_code"])
st.session_state["__annot_last_group"] = group_code
treated_clutch_id, cid = _resolve_ids_from_group(group_code)
if not cid or not treated_clutch_id:
    st.error("Could not resolve IDs for this group."); st.stop()

st.caption(f"{group_code} — {picked.iloc[0]['treatment_genotype_group']}")
st.subheader("Annotate this treated clutch group")

cur = _load_group_annotation(group_code)
row = cur.iloc[0] if not cur.empty else {}

# inputs (1–100 scale)
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    red_val = st.number_input("red_intensity (1–100)", min_value=1, max_value=100, step=1,
                              value=int(round(float(row.get("red_intensity") or 0) or 0)) or 1)
with c2:
    green_val = st.number_input("green_intensity (1–100)", min_value=1, max_value=100, step=1,
                                value=int(round(float(row.get("green_intensity") or 0) or 0)) or 1)
with c3:
    note_txt = st.text_input("note", value=str(row.get("notes") or ""), placeholder="optional")

c4, c5, c6 = st.columns([1, 1, 1])
with c4:
    gfreq_val = st.number_input("green_frequency (1–100)", min_value=1, max_value=100, step=1,
                                value=int(round(float(row.get("green_frequency") or 0) or 0)) or 1)
with c5:
    rfreq_val = st.number_input("red_frequency (1–100)", min_value=1, max_value=100, step=1,
                                value=int(round(float(row.get("red_frequency") or 0) or 0)) or 1)
with c6:
    n_val = st.number_input("n_animals (integer ≥ 0)", min_value=0, step=1,
                            value=int(row.get("n_animals") or 0))

# save
if st.button("Save annotation", width="stretch", key="save_group_annotation"):
    _update_group_annotation(
        treated_clutch_id,
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
st.subheader("Updated treated clutch group")
updated = _load_group_annotation(group_code)
if updated.empty:
    st.info("No record found (unexpected).")
else:
    show_cols = [
        "treated_clutch_code",
        "red_intensity","green_intensity",
        "green_frequency","red_frequency","n_animals",
        "notes",
        "annotated_by","annotated_at",
    ]
    st.dataframe(updated[[c for c in show_cols if c in updated.columns]], width="stretch", hide_index=True)