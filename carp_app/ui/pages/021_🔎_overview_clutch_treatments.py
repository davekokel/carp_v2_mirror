# =============================================================================
# 🔎 Overview — Clutch instances (canonical resolved view)
#   - Source: public.v_clutch_instances_resolved (joins v_clutch_treatments)
#   - Simple filters, selectable grid, and details (treatments + annotations)
# =============================================================================
from __future__ import annotations
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy import text as _sql

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

from carp_app.ui.lib.app_ctx import get_engine as _create_engine

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()
st.set_page_config(page_title="🔎 Overview — Clutch instances", page_icon="🐣", layout="wide")
st.title("🔎 Overview — Clutch instances")

# ── Engine (cached) ──────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()
def _eng() -> Engine:
    return _cached_engine()

# ── Config ───────────────────────────────────────────────────────────────────
# Canonical resolved view (wraps effective + v_clutch_treatments)
CLUTCHES_VIEW = "public.v_clutch_instances_resolved"
# Generic link + registry views (for details)
CLUTCH_LINK    = "public.clutch_materials"
MATERIALS_VIEW = "public.v_materials"
# Optional legacy table (details fallback)
LEGACY_TREAT   = "public.clutch_instance_treatments"
ANNOT_TABLE    = "public.clutch_instance_annotations"

# ── Helpers ──────────────────────────────────────────────────────────────────
def _table_exists(schema: str, name: str) -> bool:
    q = _sql("""
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = :s AND table_name = :t
      LIMIT 1
    """)
    with _eng().begin() as cx:
        return cx.execute(q, {"s": schema, "t": name}).first() is not None

def _view_exists(schema: str, name: str) -> bool:
    q = _sql("""
      SELECT 1 FROM information_schema.views
      WHERE table_schema = :s AND table_name = :t
      UNION ALL
      SELECT 1 FROM pg_catalog.pg_matviews
      WHERE schemaname = :s AND matviewname = :t
      LIMIT 1
    """)
    with _eng().begin() as cx:
        return cx.execute(q, {"s": schema, "t": name}).first() is not None

def _safe(s) -> str:
    return ("" if s is None else str(s)).strip()

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1,1,1,2])
    with c1: d_from = st.date_input("From", value=today - timedelta(days=60))
    with c2: d_to   = st.date_input("To",   value=today + timedelta(days=7))
    with c3: who    = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt   = st.text_input("Search (CI/CR code, cross/clutch/genotype/strain)", value="")
    c5, c6 = st.columns([1,1])
    with c5: most_recent = st.checkbox("Most recent only (ignore dates)", value=False)
    with c6: lim = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
    submitted = st.form_submit_button("Apply", width="stretch")

# ── Data loader (resolved view + optional annotations) ───────────────────────
def _load_clutches_summary() -> pd.DataFrame:
    where, params = [], {}
    if not most_recent:
        where.append("v.created_at_instance::date BETWEEN :d1 AND :d2")
        params.update({"d1": d_from, "d2": d_to})
    if _safe(who):
        where.append("COALESCE(v.created_by_instance,'') ILIKE :who")
        params["who"] = f"%{_safe(who)}%"
    if _safe(qtxt):
        params["q"] = f"%{_safe(qtxt)}%"
        where.append("""(
            v.clutch_code ILIKE :q OR
            v.cross_name_pretty ILIKE :q OR
            COALESCE(v.treatments_genotype_effective_resolved, v.treatments_genotype_effective, '') ILIKE :q OR
            COALESCE(v.treatments_pretty_effective_resolved,  v.treatments_pretty_effective,  '') ILIKE :q OR
            COALESCE(v.clutch_genotype_effective,'') ILIKE :q
        )""")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    has_ann = _table_exists("public", ANNOT_TABLE)

    ann_join = """
      LEFT JOIN LATERAL (
        SELECT
          COUNT(*)::int AS annotations_count,
          string_agg(a.note, ' | ' ORDER BY a.created_at DESC NULLS LAST) AS annotations_notes
        FROM public.clutch_instance_annotations a
        WHERE a.clutch_instance_id = ci.id
      ) an ON TRUE
    """ if has_ann else "LEFT JOIN LATERAL (SELECT NULL::int AS annotations_count, ''::text AS annotations_notes) an ON TRUE"

    ann_sel  = "an.annotations_count, an.annotations_notes"

    sql = text(f"""
      WITH base AS (
        SELECT
          ci.id::text                      AS clutch_instance_id,
          v.clutch_code                    AS clutch_code,
          v.clutch_birthday                AS clutch_birthday,
          v.cross_name_pretty              AS cross_name_pretty,
          v.clutch_genotype_effective      AS clutch_genotype_effective,
          COALESCE(v.treatments_count_effective_resolved, 0)::int       AS treatments_count_effective,
          COALESCE(v.treatments_pretty_effective_resolved, ''::text)     AS treatments_pretty_effective,
          COALESCE(v.treatments_genotype_effective_resolved, ''::text)   AS treatments_genotype_effective,
          v.created_by_instance            AS created_by_instance,
          v.created_at_instance            AS created_at_instance,
          v.last_treatment_at              AS last_treatment_at
        FROM {CLUTCHES_VIEW} v
        JOIN public.clutch_instances ci ON ci.clutch_instance_code = v.clutch_code
        {where_sql}
        ORDER BY v.created_at_instance DESC NULLS LAST, v.clutch_code
        LIMIT :lim
      )
      SELECT
        b.*,
        {ann_sel}
      FROM base b
      JOIN public.clutch_instances ci ON ci.clutch_instance_code = b.clutch_code
      {ann_join}
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={**params, "lim": lim})

    for c in df.select_dtypes(include=["object"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _load_detail_rows(clutch_instance_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    tdf = pd.DataFrame(columns=["created_at","material_type","material_code","material_name","notes","created_by"])
    adf = pd.DataFrame(columns=["created_at","note","created_by"])
    with _eng().begin() as cx:
        if _table_exists("public", CLUTCH_LINK) and _view_exists("public", "v_materials"):
            tdf = pd.read_sql(text(f"""
              SELECT
                cm.created_at,
                cm.material_type,
                cm.material_code,
                COALESCE(cm.material_name, vm.material_name) AS material_name,
                cm.notes,
                cm.created_by
              FROM {CLUTCH_LINK} cm
              LEFT JOIN {MATERIALS_VIEW} vm
                ON lower(vm.material_type)=lower(cm.material_type)
               AND lower(vm.material_code)=lower(cm.material_code)
              WHERE cm.clutch_instance_id = CAST(:cid AS uuid)
              ORDER BY cm.created_at DESC NULLS LAST
            """), cx, params={"cid": clutch_instance_id})
        elif _table_exists("public", LEGACY_TREAT):
            tdf = pd.read_sql(text(f"""
              SELECT created_at, material_type, material_code, material_name, notes, created_by
              FROM {LEGACY_TREAT}
              WHERE clutch_instance_id = CAST(:cid AS uuid)
              ORDER BY created_at DESC NULLS LAST
            """), cx, params={"cid": clutch_instance_id})
        if _table_exists("public", ANNOT_TABLE):
            adf = pd.read_sql(text(f"""
              SELECT created_at, note, created_by
              FROM {ANNOT_TABLE}
              WHERE clutch_instance_id = CAST(:cid AS uuid)
              ORDER BY created_at DESC NULLS LAST
            """), cx, params={"cid": clutch_instance_id})
    return tdf, adf

# ── Main table (resolved fields; rollup is 4th column) ───────────────────────
df = _load_clutches_summary()
st.caption(f"{len(df)} clutch instance(s)")

if df.empty:
    st.info("No clutch instances with the current filters."); st.stop()

tbl = df.copy()
cols = [
    "clutch_code",                                # 1
    "clutch_birthday",                            # 2
    "cross_name_pretty",                          # 3
    "treatments_genotype_effective",              # 4 ← Treatments > genotype (resolved already)
    "treatments_count_effective",                 # 5
    "treatments_pretty_effective",                # 6
]
for c in cols:
    if c not in tbl.columns:
        tbl[c] = ""

table = tbl[cols].copy()
table.insert(0, "✓ Select", False)

st.subheader("Clutch instances")
grid = st.data_editor(
    table,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config={
        "✓ Select":                      st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday":               st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
        "treatments_genotype_effective": st.column_config.TextColumn("Treatments > genotype", disabled=True),
        "treatments_count_effective":    st.column_config.NumberColumn("n treatments", disabled=True),
        "treatments_pretty_effective":   st.column_config.TextColumn("treatments_pretty", disabled=True),
    },
    key="overview_ci_v1",
)

# Map selection back to the full df using clutch_code
sel_mask = grid.get("✓ Select", pd.Series(False, index=grid.index)).fillna(False).astype(bool)
picked_codes = table.loc[sel_mask, "clutch_code"].tolist()
picked = df[df["clutch_code"].isin(picked_codes)].reset_index(drop=True)

# ── Details pane ─────────────────────────────────────────────────────────────
st.subheader("Details")
if picked.empty:
    st.info("Select a row above to view linked treatments and annotations.")
else:
    row = picked.iloc[0]
    cid = row.get("clutch_instance_id") or ""
    st.caption(f"Clutch instance: {row.get('clutch_code','')} • Created: {row.get('created_at_instance','')}")
    tdf, adf = _load_detail_rows(cid)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Treatments**")
        if tdf.empty:
            st.info("No treatments linked.")
        else:
            st.dataframe(tdf, width="stretch", hide_index=True)

    with c2:
        st.markdown("**Annotations**")
        if not _table_exists("public", ANNOT_TABLE):
            st.caption("Annotations table not installed.")
        elif adf.empty:
            st.info("No annotations linked.")
        else:
            st.dataframe(adf, width="stretch", hide_index=True)