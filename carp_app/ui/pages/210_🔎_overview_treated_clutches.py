# carp_app/ui/pages/210_🧪_overview_treated_clutches.py
# 🔎 Overview — Clutch treatments (parents + per-clutch treatments summary)
from __future__ import annotations

import sys, pathlib
from datetime import date, timedelta
from typing import Any, Set

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

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
from carp_app.ui.lib.page_engine import engine

# --- auth / page --------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — 🔎 Overview: Clutch treatments",
                   page_icon="🧪", layout="wide")
st.title("🔎 Overview — Clutch treatments")

with engine().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# --- object names you actually have ------------------------------------------
V_TCL_OV   = "public.v_treated_clutches_overview"  # one row per treated group (just created)
T_TCL      = "public.treated_clutches"             # treated groups
T_JCT      = "public.join_clutch_treatments"       # link treated_clutches -> treatments
T_TX       = "public.treatments"                   # kind_code, treat_code, treat_text

# --- helpers ------------------------------------------------------------------
def _exists_view(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = text(
        "SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n "
        "UNION ALL SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n LIMIT 1"
    )
    with engine().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _exists_table(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = text("SELECT 1 FROM information_schema.tables WHERE table_schema=:s AND table_name=:n LIMIT 1")
    with engine().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _safe(cx, q: str | TextClause, p: dict[str, Any] | None = None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

# --- filters ------------------------------------------------------------------
today = date.today()
with st.form("filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1: d_from = st.date_input("From", value=today - timedelta(days=60))
    with c2: d_to   = st.date_input("To",   value=today + timedelta(days=7))
    with c3: who    = st.text_input("Created by (plan/instance)", "")
    with c4: qtxt   = st.text_input("Search (group/clutch/cross/genotype/treatments/parents)", "")
    c5, c6 = st.columns([1, 1])
    with c5: most_recent = st.checkbox("Most recent (ignore dates)", value=False)
    with c6: lim = st.number_input("Limit", min_value=1, max_value=1000, value=500, step=50)
    st.form_submit_button("Apply", use_container_width=True)

# --- data loader (thin: just select from the view) ----------------------------
def _require_objects():
    if not _exists_view(V_TCL_OV):
        st.error(f"Required view {V_TCL_OV} not found. Apply the migration for v_treated_clutches_overview first."); st.stop()
    if not _exists_table(T_TCL) or not _exists_table(T_JCT) or not _exists_table(T_TX):
        st.error("Required tables treated_clutches / join_clutch_treatments / treatments not found."); st.stop()

def _load_groups() -> pd.DataFrame:
    _require_objects()
    where, params = [], {}
    if not most_recent:
        where.append("group_created_at::date BETWEEN :d1 AND :d2"); params.update({"d1": d_from, "d2": d_to})
    if qtxt.strip():
        params["q"] = f"%{qtxt.strip()}%"
        where.append("""(
          treated_clutch_code ILIKE :q OR
          clutch_code         ILIKE :q OR
          cross_code          ILIKE :q OR
          COALESCE(clutch_genotype,'')        ILIKE :q OR
          COALESCE(treatments_codes_group,'') ILIKE :q OR
          COALESCE(treatments_names_group,'') ILIKE :q OR
          COALESCE(mom_fish_code,'')          ILIKE :q OR
          COALESCE(dad_fish_code,'')          ILIKE :q OR
          COALESCE(mom_genotype,'')           ILIKE :q OR
          COALESCE(dad_genotype,'')           ILIKE :q
        )""")
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    params["lim"] = int(lim)

    sql = text(f"""
      SELECT *
      FROM {V_TCL_OV}
      {where_sql}
      ORDER BY clutch_code, group_created_at
      LIMIT :lim
    """)
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # derive legacy columns this page previously expected
    if "clutch_birthday" not in df.columns:
        df["clutch_birthday"] = pd.NaT
    df["cross_parents_codes_pretty"] = (df.get("mom_fish_code", "").fillna("") + " × " +
                                        df.get("dad_fish_code", "").fillna(""))
    df["cross_parents_genotypes_pretty"] = (df.get("mom_genotype", "").fillna("") + " × " +
                                            df.get("dad_genotype", "").fillna(""))
    if "clutch_genotype_pretty" not in df.columns and "clutch_genotype" in df.columns:
        df["clutch_genotype_pretty"] = df["clutch_genotype"].fillna("")

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

df = _load_groups()
st.caption(f"{len(df)} treated clutch group(s)")
if df.empty:
    st.info("No treated clutch groups with the current filters."); st.stop()

# --- main grid (per treated group) -------------------------------------------
cols = [
    "treated_clutch_code", "group_created_at",
    "treatments_count_group",
    "treatments_codes_group", "treatments_names_group",
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
    hide_index=True, use_container_width=True, num_rows="fixed",
    column_config={
        "✓ Select":                   st.column_config.CheckboxColumn("✓", default=False),
        "group_created_at":           st.column_config.DatetimeColumn("created_at", disabled=True),
        "treatments_count_group":     st.column_config.NumberColumn("# tx", disabled=True, format="%d"),
        "treatments_codes_group":     st.column_config.TextColumn("Tx (codes)", disabled=True),
        "treatments_names_group":     st.column_config.TextColumn("Tx (names)", disabled=True),
        "clutch_birthday":            st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
        "cross_parents_codes_pretty": st.column_config.TextColumn("Parents (codes)", disabled=True),
        "cross_parents_genotypes_pretty": st.column_config.TextColumn("Parents (genotypes)", disabled=True),
        "clutch_genotype_pretty":     st.column_config.TextColumn("Offspring genotype", disabled=True),
    },
    key="overview_treated_clutches_v3",
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

# summary table
summary = [
    {"Field":"treated_clutch_code","Value":group_code},
    {"Field":"created_at","Value":row.get("group_created_at")},
    {"Field":"Tx (codes)","Value":row.get("treatments_codes_group")},
    {"Field":"Tx (names)","Value":row.get("treatments_names_group")},
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
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

# Treatments rows (by group) from base tables
def _load_detail_rows_by_group(treated_clutch_code: str) -> pd.DataFrame:
    if not treated_clutch_code:
        return pd.DataFrame()
    sql = text(f"""
      SELECT
        jct.created_at,
        t.kind_code                           AS tx_type,
        t.treat_code                          AS tx_code,
        COALESCE(t.treat_text, t.treat_code)  AS tx_name
      FROM {T_TCL} tc
      JOIN {T_JCT} jct ON jct.treated_clutch_id = tc.id
      LEFT JOIN {T_TX}  t   ON t.id = jct.treatment_id
      WHERE tc.treated_clutch_code = :g
      ORDER BY jct.created_at DESC NULLS LAST
    """)
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"g": treated_clutch_code})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

tdf = _load_detail_rows_by_group(group_code)
with cB:
    st.markdown("**Group treatments (rows)**")
    if tdf.empty:
        st.caption("No treatments in this group.")
    else:
        st.dataframe(tdf, hide_index=True, use_container_width=True)

st.markdown("---")
st.markdown("**Treatments (rows)**")
if tdf.empty:
    st.info("No treatments linked.")
else:
    st.dataframe(tdf, hide_index=True, use_container_width=True)