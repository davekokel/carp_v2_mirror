# =============================================================================
# 🔎 Overview — Clutch treatments (current contract: v_clutch_instances + join_clutch_treatments)
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
st.set_page_config(page_title="🔎 Overview — Clutch treatments", page_icon="🐣", layout="wide")
st.title("🔎 Overview — Clutch treatments")

# ── Engine (cached) ──────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()
def _eng() -> Engine:
    return _cached_engine()

# ── Config (current design) ──────────────────────────────────────────────────
CLUTCHES_VIEW = "public.v_clutch_instances"            # contract columns exist here
CLUTCH_LINK   = "public.join_clutch_treatments"        # canonical join (no v_materials)
ANNOT_TABLE   = "public.clutch_instance_annotations"    # optional

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

def _rollup_fallback(treat_pretty: str|None, clutch_geno: str|None) -> str:
    t = (treat_pretty or "").strip()
    g = (clutch_geno or "").strip()
    if t and g:
        return f"{t} > {g}"
    return t or g

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
    _ = st.form_submit_button("Apply", width="stretch")

# ── Data loader (uses current v_clutch_instances contract) ───────────────────
def _load_clutches_summary() -> pd.DataFrame:
    if not _view_exists("public", CLUTCHES_VIEW.split(".")[1]):
        st.error(f"Required view {CLUTCHES_VIEW} not found."); st.stop()

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
            COALESCE(v.genotype_treatment_rollup_effective,'') ILIKE :q OR
            COALESCE(v.treatments_pretty_effective,'') ILIKE :q OR
            COALESCE(v.clutch_genotype_pretty,'') ILIKE :q
        )""")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    # We’ll resolve clutch_instance_id later; here we pull only from the view.
    sql = text(f"""
      SELECT
        v.clutch_code,
        v.clutch_birthday,
        v.cross_name_pretty,
        v.clutch_name,
        v.clutch_genotype_pretty,
        v.clutch_strain_pretty,
        COALESCE(v.treatments_count_effective, 0)::int      AS treatments_count_effective,
        COALESCE(v.treatments_pretty_effective, ''::text)   AS treatments_pretty_effective,
        COALESCE(v.genotype_treatment_rollup_effective,''::text) AS genotype_treatment_rollup_effective,
        v.created_by_instance,
        v.created_at_instance
      FROM {CLUTCHES_VIEW} v
      {where_sql}
      ORDER BY v.created_at_instance DESC NULLS LAST, v.clutch_code
      LIMIT :lim
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={**params, "lim": lim})

    # UI-friendly strings
    for c in df.select_dtypes(include=["object"]).columns:
        df[c] = df[c].astype("string").fillna("")

    # Build the display rollup (prefer effective; else treatments > genotype)
    disp = []
    for _, r in df.iterrows():
        eff = (r.get("genotype_treatment_rollup_effective") or "").strip()
        if eff:
            disp.append(eff)
        else:
            disp.append(_rollup_fallback(r.get("treatments_pretty_effective"), r.get("clutch_genotype_pretty")))
    df["treatments_genotype_display"] = pd.Series(disp, dtype="string")

    return df

def _resolve_clutch_instance_id(clutch_code: str) -> str | None:
    sql = text("""
      SELECT id::text
      FROM public.clutch_instances
      WHERE clutch_instance_code = :code
      LIMIT 1
    """)
    with _eng().begin() as cx:
        row = cx.execute(sql, {"code": clutch_code}).scalar()
    return row or None

def _load_detail_rows(clutch_code: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cid = _resolve_clutch_instance_id(clutch_code)
    if not cid:
        return pd.DataFrame(), pd.DataFrame()

    tdf = pd.DataFrame(columns=["created_at","treatment_type","treatment_code","treatment_name","notes","created_by"])
    adf = pd.DataFrame(columns=["created_at","note","created_by"])

    with _eng().begin() as cx:
        if _table_exists("public", CLUTCH_LINK.split(".")[1]):
            tdf = pd.read_sql(text(f"""
              SELECT created_at, treatment_type, treatment_code, treatment_name, notes, created_by
              FROM {CLUTCH_LINK}
              WHERE clutch_instance_id = CAST(:cid AS uuid)
              ORDER BY created_at DESC NULLS LAST
            """), cx, params={"cid": cid})

        if _table_exists("public", ANNOT_TABLE.split(".")[1]):
            adf = pd.read_sql(text(f"""
              SELECT created_at, note, created_by
              FROM {ANNOT_TABLE}
              WHERE clutch_instance_id = CAST(:cid AS uuid)
              ORDER BY created_at DESC NULLS LAST
            """), cx, params={"cid": cid})

    for df in (tdf, adf):
        for c in df.select_dtypes(include=["object"]).columns:
            df[c] = df[c].astype("string").fillna("")
    return tdf, adf

# ── Main table ────────────────────────────────────────────────────────────────
df = _load_clutches_summary()
st.caption(f"{len(df)} clutch instance(s)")

if df.empty:
    st.info("No clutch instances with the current filters."); st.stop()

tbl = df.copy()
cols = [
    "clutch_code",
    "clutch_birthday",
    "cross_name_pretty",
    "treatments_genotype_display",      # 4: Treatments > genotype (display)
    "treatments_count_effective",
    "treatments_pretty_effective",
]
for c in cols:
    if c not in tbl.columns:
        tbl[c] = ""

grid_src = tbl[cols].copy()
grid_src.insert(0, "✓ Select", False)

st.subheader("Clutch instances")
grid = st.data_editor(
    grid_src,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config={
        "✓ Select":                      st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday":               st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
        "treatments_genotype_display":   st.column_config.TextColumn("Treatments > genotype", disabled=True),
        "treatments_count_effective":    st.column_config.NumberColumn("n treatments", disabled=True),
        "treatments_pretty_effective":   st.column_config.TextColumn("treatments_pretty", disabled=True),
    },
    key="overview_ci_v2",
)

sel_mask = grid.get("✓ Select", pd.Series(False, index=grid.index)).fillna(False).astype(bool)
picked_codes = grid_src.loc[sel_mask, "clutch_code"].tolist()
picked = df[df["clutch_code"].isin(picked_codes)].reset_index(drop=True)

# ── Details pane ─────────────────────────────────────────────────────────────
st.subheader("Details")
if picked.empty:
    st.info("Select a row above to view linked treatments and annotations.")
else:
    row = picked.iloc[0]
    code = row.get("clutch_code", "")
    st.caption(f"Clutch: {code} • Created: {row.get('created_at_instance','')}")

    tdf, adf = _load_detail_rows(code)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Treatments**")
        if tdf.empty:
            st.info("No treatments linked.")
        else:
            st.dataframe(tdf, width="stretch", hide_index=True)

    with c2:
        st.markdown("**Annotations**")
        if not _table_exists("public", ANNOT_TABLE.split(".")[1]):
            st.caption("Annotations table not installed.")
        elif adf.empty:
            st.info("No annotations linked.")
        else:
            st.dataframe(adf, width="stretch", hide_index=True)