# =============================================================================
# 🔎 Overview — Clutch treatments (parents + per-clutch treatments summary)
# Requires:
#   • public.v_clutch_instances (pretties + treatment_genotype + counts)
#   • public.clutch_instances
#   • public.crosses
#   • public.v_tank_pairs
# Optional:
#   • public.v_clutch_annotations_pivot  (or public.v_clutch_annotations)
# =============================================================================
from __future__ import annotations
import os, sys, pathlib
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy import text as _sql
from sqlalchemy.engine import Engine

# --- project wiring -----------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine as _create_engine

# --- auth / page --------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🔎 Overview — Clutch treatments",
                   page_icon="🧪", layout="wide")
st.title("🔎 Overview — Clutch treatments")

# --- engine -------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _create_engine()

# --- object names -------------------------------------------------------------
V_CLUTCH   = "public.v_clutch_instances"
T_CLUTCH   = "public.clutch_instances"
T_CROSSES  = "public.crosses"
V_TPAIRS   = "public.v_tank_pairs"
T_JCT      = "public.join_clutch_treatments"
V_ANN      = "public.v_clutch_annotations_pivot"
V_ANN_ALT  = "public.v_clutch_annotations"
V_TCLUTCH = "public.v_treated_clutches"

# --- helpers ------------------------------------------------------------------
def _exists_view(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = _sql(
        "SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n "
        "UNION ALL SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n LIMIT 1"
    )
    with _eng().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _exists_table(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = _sql("SELECT 1 FROM information_schema.tables WHERE table_schema=:s AND table_name=:n LIMIT 1")
    with _eng().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _resolve_clutch_id(clutch_code: str) -> str | None:
    sql = text("SELECT id::text FROM public.clutch_instances WHERE clutch_instance_code=:c LIMIT 1")
    with _eng().begin() as cx:
        return cx.execute(sql, {"c": clutch_code}).scalar()

def _load_detail_rows(clutch_code: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Treatments (rows) + optional annotation pivot for a selected clutch."""
    cid = _resolve_clutch_id(clutch_code)
    if not cid:
        return pd.DataFrame(), pd.DataFrame()

    with _eng().begin() as cx:
        if _exists_table(T_JCT):
            tdf = pd.read_sql(
                text(f"""
                    SELECT created_at,
                           treatment_type  AS tx_type,
                           treatment_code  AS tx_code,
                           treatment_name  AS tx_name,
                           notes,
                           created_by
                    FROM {T_JCT}
                    WHERE clutch_instance_id = CAST(:cid AS uuid)
                    ORDER BY created_at DESC NULLS LAST
                """),
                cx, params={"cid": cid}
            )
        else:
            tdf = pd.DataFrame()

        ann_view = V_ANN if _exists_view(V_ANN) else (V_ANN_ALT if _exists_view(V_ANN_ALT) else None)
        if ann_view:
            ap = pd.read_sql(
                text(f"""
                    SELECT * FROM {ann_view}
                    WHERE clutch_code = (SELECT clutch_instance_code FROM {T_CLUTCH} WHERE id=CAST(:cid AS uuid))
                    LIMIT 1
                """),
                cx, params={"cid": cid}
            )
        else:
            ap = pd.DataFrame()

    for df in (tdf, ap):
        if not df.empty:
            for c in df.select_dtypes(include="object").columns:
                df[c] = df[c].astype("string").fillna("")
    return tdf, ap

def _load_detail_rows_by_group(treated_clutch_code: str) -> pd.DataFrame:
    if not treated_clutch_code:
        return pd.DataFrame()
    sql = text("""
      SELECT
        jct.created_at,
        jct.treatment_type  AS tx_type,
        jct.treatment_code  AS tx_code,
        jct.treatment_name  AS tx_name,
        jct.notes,
        jct.created_by
      FROM public.join_clutch_treatments jct
      JOIN public.treated_clutches tc ON tc.id = jct.treated_clutch_id
      WHERE tc.treated_clutch_code = :g
      ORDER BY jct.created_at DESC NULLS LAST
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"g": treated_clutch_code})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

# --- filters ------------------------------------------------------------------
with _eng().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1: d_from = st.date_input("From", value=today - timedelta(days=60))
    with c2: d_to   = st.date_input("To",   value=today + timedelta(days=7))
    with c3: who    = st.text_input("Created by (plan/instance)", "")
    with c4: qtxt   = st.text_input("Search (CI/CR/cross/clutch/genotype/treatments)", "")
    c5, c6 = st.columns([1, 1])
    with c5: most_recent = st.checkbox("Most recent (ignore dates)", value=False)
    with c6: lim = st.number_input("Limit", min_value=1, max_value=1000, value=500, step=50)
    st.form_submit_button("Apply", width="stretch")

# --- data loader --------------------------------------------------------------
def _load_groups() -> pd.DataFrame:
    # require the group view + context tables
    for obj in (V_TCLUTCH, T_CLUTCH, T_CROSSES, V_TPAIRS):
        ok = _exists_view(obj) if obj.startswith("public.v_") else _exists_table(obj)
        if not ok:
            st.error(f"Required object not found: {obj}"); st.stop()

    where, params = [], {}
    if not most_recent:
        where.append("vt.group_created_at::date BETWEEN :d1 AND :d2")
        params.update({"d1": d_from, "d2": d_to})
    if qtxt.strip():
        params["q"] = f"%{qtxt.strip()}%"
        where.append("""
          (
            vt.treated_clutch_code ILIKE :q OR
            vt.clutch_code         ILIKE :q OR
            vt.cross_name_pretty   ILIKE :q OR
            COALESCE(tp.mom_fish_code,'') ILIKE :q OR
            COALESCE(tp.dad_fish_code,'') ILIKE :q OR
            COALESCE(tp.mom_genotype,'')  ILIKE :q OR
            COALESCE(tp.dad_genotype,'')  ILIKE :q OR
            COALESCE(vt.clutch_genotype_pretty,'')   ILIKE :q OR
            COALESCE(vt.treatments_codes_group,'')   ILIKE :q OR
            COALESCE(vt.treatments_names_group,'')   ILIKE :q OR
            COALESCE(vt.treatment_genotype_group,'') ILIKE :q
          )
        """)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    params["lim"] = int(lim)

    sql = text(f"""
      WITH ci_map AS (
        SELECT id AS clutch_id, clutch_instance_code AS clutch_code, cross_instance_id
        FROM {T_CLUTCH}
      )
      SELECT
        vt.treated_clutch_code,             -- FIRST IN GRID
        vt.group_created_at,
        vt.treatments_count_group::int AS treatments_count_group,
        vt.treatments_codes_group,
        vt.treatments_names_group,
        vt.treatment_genotype_group,

        vt.clutch_code,
        vt.clutch_birthday,
        vt.cross_name_pretty,
        vt.clutch_genotype_pretty,

        CONCAT(COALESCE(tp.mom_fish_code,''), ' × ', COALESCE(tp.dad_fish_code,'')) AS cross_parents_codes_pretty,
        CONCAT(COALESCE(tp.mom_genotype,''),  ' × ', COALESCE(tp.dad_genotype,''))  AS cross_parents_genotypes_pretty

      FROM {V_TCLUTCH} vt
      LEFT JOIN ci_map m  ON m.clutch_code = vt.clutch_code
      LEFT JOIN {T_CROSSES} x ON x.id = m.cross_instance_id
      LEFT JOIN {V_TPAIRS}  tp ON tp.tank_pair_code = x.tank_pair_code
      {where_sql}
      ORDER BY
        vt.clutch_code,
        (regexp_match(vt.treated_clutch_code, '\\-(\\d+)$'))[1]::int ASC,
        vt.group_created_at ASC
        LIMIT :lim
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

df = _load_groups()
st.caption(f"{len(df)} treated clutch group(s)")
if df.empty:
    st.info("No clutch instances with the current filters."); st.stop()

# --- main grid ----------------------------------------------------------------
# --- main grid (per treated group) -------------------------------------------
cols = [
    "treated_clutch_code", "group_created_at",        # first columns
    "treatments_count_group",
    "treatments_codes_group", "treatments_names_group",
    "treatment_genotype_group",
    "clutch_code", "clutch_birthday",
    "cross_parents_codes_pretty", "cross_parents_genotypes_pretty",
    "clutch_genotype_pretty",
]
grid_src = df[cols].copy()
if "✓ Select" not in grid_src.columns:
    grid_src.insert(0, "✓ Select", False)

st.subheader("Treated clutch groups")
grid = st.data_editor(
    grid_src,
    hide_index=True, width="stretch", num_rows="fixed",
    column_config={
        "✓ Select":                   st.column_config.CheckboxColumn("✓", default=False),
        "group_created_at":           st.column_config.DatetimeColumn("created_at", disabled=True),
        "treatments_count_group":     st.column_config.NumberColumn("# tx", disabled=True, format="%d"),
        "treatments_codes_group":     st.column_config.TextColumn("Tx (codes)", disabled=True),
        "treatments_names_group":     st.column_config.TextColumn("Tx (names)", disabled=True),
        "treatment_genotype_group":   st.column_config.TextColumn("Tx > Genotype", disabled=True),
        "clutch_birthday":            st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
        "cross_parents_codes_pretty": st.column_config.TextColumn("Parents (codes)", disabled=True),
        "cross_parents_genotypes_pretty": st.column_config.TextColumn("Parents (genotypes)", disabled=True),
        "clutch_genotype_pretty":     st.column_config.TextColumn("Offspring genotype", disabled=True),
    },
    key="overview_treated_clutches_v2",
)

sel_mask = grid.get("✓ Select", pd.Series(False, index=grid.index)).fillna(False).astype(bool)
picked_groups = grid.loc[sel_mask, "treated_clutch_code"].tolist()
picked = df[df["treated_clutch_code"].isin(picked_groups)].reset_index(drop=True)

st.subheader("Details")
if picked.empty:
    st.info("Select a row above to view linked details."); st.stop()

row = picked.iloc[0]
code = row.get("clutch_code", "")
group_code = row.get("treated_clutch_code", "")

st.caption(f"Group: {group_code} • Clutch: {code}")

# summary table (same as before but using group fields)
summary = [
    {"Field":"treated_clutch_code","Value":group_code},
    {"Field":"created_at","Value":row.get("group_created_at")},
    {"Field":"Tx (codes)","Value":row.get("treatments_codes_group")},
    {"Field":"Tx (names)","Value":row.get("treatments_names_group")},
    {"Field":"Tx > Genotype","Value":row.get("treatment_genotype_group")},
    {"Field":"Clutch code","Value":code},
    {"Field":"Clutch birthday","Value":row.get("clutch_birthday")},
    {"Field":"Parents (codes)","Value":row.get("cross_parents_codes_pretty")},
    {"Field":"Parents (genotypes)","Value":row.get("cross_parents_genotypes_pretty")},
    {"Field":"Offspring genotype","Value":row.get("clutch_genotype_pretty")},
]
summary_df = pd.DataFrame([d for d in summary if str(d["Value"] or "").strip()])

cA, cB = st.columns([1, 1])
with cA:
    st.markdown("**Group summary**")
    st.dataframe(summary_df, hide_index=True, width="stretch")

# Treatments rows (by group)
tdf = _load_detail_rows_by_group(group_code)
with cB:
    st.markdown("**Group treatments (rows)**")
    if tdf.empty:
        st.caption("No treatments in this group.")
    else:
        st.dataframe(tdf, hide_index=True, width="stretch")

st.markdown("---")
st.markdown("**Treatments (rows)**")
if tdf.empty:
    st.info("No treatments linked.")
else:
    st.dataframe(tdf, hide_index=True, width="stretch")