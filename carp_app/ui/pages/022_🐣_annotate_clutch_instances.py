# carp_app/ui/pages/020_🧪_annotate_clutch_instances.py
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
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

st.set_page_config(page_title="🐣 Annotate Clutch Instances", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Clutch Instances")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

# ─────────────────────────────────────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────────────────────────────────────
def _load_clutches_filtered(d1: date, d2: date, created_by: str, qtxt: str, ignore_dates: bool) -> pd.DataFrame:
    """
    Source of truth: public.v_clutch_instances_display
    Extra search keys: mom/dad fish codes via v_cross_clutch_instances
    """
    where_bits, params = [], {}
    if not ignore_dates:
        where_bits.append("v.created_at_instance::date BETWEEN :d1 AND :d2")
        params["d1"], params["d2"] = d1, d2
    if (created_by or "").strip():
        where_bits.append("COALESCE(v.created_by_instance,'') ILIKE :byl")
        params["byl"] = f"%{created_by.strip()}%"
    if (qtxt or "").strip():
        where_bits.append("""(
          COALESCE(v.clutch_code,'')                        ILIKE :ql OR
          COALESCE(v.cross_name_pretty,'')                  ILIKE :ql OR
          COALESCE(v.clutch_name,'')                        ILIKE :ql OR
          COALESCE(v.clutch_genotype_pretty,'')             ILIKE :ql OR
          COALESCE(v.clutch_strain_pretty,'')               ILIKE :ql OR
          COALESCE(v.treatments_pretty_effective,'')        ILIKE :ql OR
          COALESCE(v.genotype_treatment_rollup_effective,'') ILIKE :ql OR
          COALESCE(cci.mom_fish_code,'')                    ILIKE :ql OR
          COALESCE(cci.dad_fish_code,'')                    ILIKE :ql
        )""")
        params["ql"] = f"%{qtxt.strip()}%"
    where_sql = ("WHERE " + " AND ".join(where_bits)) if where_bits else ""

    sql = text(f"""
      WITH base AS (
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
        FROM public.v_clutch_instances_display v
        LEFT JOIN public.v_cross_clutch_instances cci
          ON cci.clutch_code = v.clutch_code
        {where_sql}
        ORDER BY v.created_at_instance DESC NULLS LAST, v.clutch_code
        LIMIT 500
      )
      SELECT * FROM base
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # normalize types used by the grid
    for c in [
        "clutch_name",
        "clutch_genotype_pretty",
        "genotype_treatment_rollup_effective",
        "treatments_pretty_effective",
        "cross_name_pretty",
        "created_by_instance",
    ]:
        if c in df.columns:
            df[c] = df[c].astype("string").fillna("")
    if "treatments_count_effective" in df.columns:
        df["treatments_count_effective"] = (
            pd.to_numeric(df["treatments_count_effective"], errors="coerce")
            .fillna(0)
            .astype(int)
        )

    return df.loc[:, ~df.columns.duplicated()]

def _resolve_ci_id(ci_code: str) -> Optional[str]:
    if not ci_code or not isinstance(ci_code, str):
        return None
    with eng.begin() as cx:
        # exact match
        df = pd.read_sql(
            text("""
              SELECT id::text AS clutch_instance_id
              FROM public.clutch_instances
              WHERE clutch_instance_code = :ci
              LIMIT 1
            """),
            cx,
            params={"ci": ci_code},
        )
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
        # forgiving match (strip CI-/suffix)
        df = pd.read_sql(
            text("""
              SELECT id::text AS clutch_instance_id
              FROM public.clutch_instances
              WHERE upper(regexp_replace(COALESCE(clutch_instance_code,''), '-[0-9]{2}$','')) =
                    upper(regexp_replace(:ci, '^CI-',''))
              LIMIT 1
            """),
            cx,
            params={"ci": ci_code},
        )
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
        # fallback via cross run code
        df = pd.read_sql(
            text("""
              SELECT ci.id::text AS clutch_instance_id
              FROM public.clutch_instances ci
              JOIN public.cross_instances x ON x.id = ci.cross_instance_id
              WHERE upper(regexp_replace(x.cross_run_code, '-[0-9]{2}$','')) =
                    upper(regexp_replace(:ci, '^CI-',''))
              ORDER BY ci.created_at DESC NULLS LAST
              LIMIT 1
            """),
            cx,
            params={"ci": ci_code},
        )
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
    return None

def _load_ci_annotation(cid: str) -> pd.DataFrame:
    sql = text("""
      SELECT
        id::text         AS clutch_instance_id,
        clutch_instance_code,
        label,
        red_intensity,
        green_intensity,
        notes,
        red_selected,
        green_selected,
        annotated_by,
        annotated_at,
        created_at
      FROM public.clutch_instances
      WHERE id = CAST(:cid AS uuid)
      LIMIT 1
    """)
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params={"cid": cid})

def _update_ci_annotation(cid: str, red: str, green: str, note: str, fallback_user: str):
    sql = text("""
      UPDATE public.clutch_instances
      SET
        red_intensity   = NULLIF(:red,''),
        green_intensity = NULLIF(:green,''),
        notes           = NULLIF(:note,''),
        red_selected    = CASE WHEN NULLIF(:red,'')   IS NOT NULL THEN TRUE ELSE FALSE END,
        green_selected  = CASE WHEN NULLIF(:green,'') IS NOT NULL THEN TRUE ELSE FALSE END,
        annotated_by    = COALESCE(current_setting('app.user', TRUE), :fallback_user),
        annotated_at    = now()
      WHERE id = CAST(:cid AS uuid)
    """)
    with eng.begin() as cx:
        cx.execute(sql, {
            "cid": cid,
            "red": red,
            "green": green,
            "note": note,
            "fallback_user": (getattr(user, "email", "") or fallback_user or ""),
        })

# ─────────────────────────────────────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: created_by = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt = st.text_input("Search (code/cross/clutch/genotype/strain)", value="")
    r1, r2 = st.columns([1,3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", width="stretch")

clutches = _load_clutches_filtered(d1, d2, created_by, qtxt, ignore_dates)
st.caption(f"{len(clutches)} clutch(es)")

if clutches.empty:
    st.info("No clutches found with the current filters."); st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Picker grid
# ─────────────────────────────────────────────────────────────────────────────
view_cols = [
    "clutch_code",
    "cross_name_pretty",
    "clutch_name",
    "clutch_genotype_pretty",
    "genotype_treatment_rollup_effective",   # arrow string
    "treatments_count_effective",
    "treatments_pretty_effective",
    "clutch_birthday",
    "created_by_instance",
]
have = [c for c in view_cols if c in clutches.columns]
dfv = clutches[have].copy()
dfv = dfv.loc[:, ~dfv.columns.duplicated()]
if "treatments_count_effective" in dfv.columns:
    dfv["treatments_count_effective"] = (
        pd.to_numeric(dfv["treatments_count_effective"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

last_ci = st.session_state.get("__annot_last_ci")
dfv.insert(0, "✓ Select", False)
if last_ci and "clutch_code" in dfv.columns:
    dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config={...},
    key="annotate_ci_picker_v1",
    column_order=["✓ Select"] + view_cols,
    use_container_width=True,
)

sel_mask = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False).astype(bool)
picked = dfv.loc[sel_mask, :].reset_index(drop=True)

if picked.empty:
    st.info("Select a clutch instance row to annotate it.")
    st.stop()

ci_code = str(picked.iloc[0].get("clutch_code", "")).strip()
st.session_state["__annot_last_ci"] = ci_code

# Allow either CI-… or CL(…) codes; resolve to clutch_instance_id
cid = _resolve_ci_id(ci_code)
if not cid:
    st.error("Could not resolve clutch_instance_id from this code."); st.stop()

st.subheader("Annotate this clutch instance")
current = _load_ci_annotation(cid)
cur = current.iloc[0] if not current.empty else {}

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    red_txt = st.text_input("red", value=str(cur.get("red_intensity") or ""), placeholder="text")
with c2:
    green_txt = st.text_input("green", value=str(cur.get("green_intensity") or ""), placeholder="text")
with c3:
    note_txt = st.text_input("note", value=str(cur.get("notes") or ""), placeholder="optional")

save_col, = st.columns([1])
with save_col:
    if st.button("Save annotation", width="stretch", key="save_ci_annotation"):
        _update_ci_annotation(cid, red_txt, green_txt, note_txt, fallback_user=(getattr(user, "email", "") or ""))
        st.success("Annotation saved.")

st.subheader("Updated clutch instance")
updated = _load_ci_annotation(cid)
if updated.empty:
    st.info("No record found (unexpected).")
else:
    show_cols = [
        "clutch_instance_code", "label", "red_intensity", "green_intensity", "notes",
        "red_selected", "green_selected", "annotated_by", "annotated_at", "created_at",
    ]
    present = [c for c in show_cols if c in updated.columns]
    st.dataframe(updated[present], width="stretch", hide_index=True)