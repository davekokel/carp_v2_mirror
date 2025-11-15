# carp_app/ui/pages/210_🧪_overview_treated_clutches.py
# 🔎 Overview — Clutch treatments (parents + per-clutch treatments summary)

from __future__ import annotations

import sys, pathlib
from datetime import date, timedelta
from typing import Any, List, Tuple

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

V_TCL_OV = "public.v_treated_clutches_overview"

# --- auth / page --------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🔎 Overview: Clutch treatments",
    page_icon="🧪",
    layout="wide",
)
st.title("🔎 Overview — Clutch treatments")

with engine().begin() as cx:
    dbg = pd.read_sql(
        text("select current_database() db, inet_server_addr() host, current_user u"),
        cx,
    )
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# --- helpers ------------------------------------------------------------------
def _safe(cx, q: str | TextClause, p: dict[str, Any] | None = None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

def _exists_view(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = text(
        "SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n "
        "UNION ALL "
        "SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n "
        "LIMIT 1"
    )
    with engine().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

# --- filters ------------------------------------------------------------------
today = date.today()
with st.form("filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        d_from = st.date_input("From", value=today - timedelta(days=60))
    with c2:
        d_to = st.date_input("To", value=today + timedelta(days=7))
    with c3:
        who = st.text_input("Created by (plan/instance)", "")
    with c4:
        qtxt = st.text_input(
            "Search (group/clutch/cross/genotype/treatments/parents)",
            "",
        )
    c5, c6 = st.columns([1, 1])
    with c5:
        most_recent = st.checkbox("Most recent (ignore dates)", value=False)
    with c6:
        lim = st.number_input("Limit", min_value=1, max_value=1000, value=500, step=50)
    st.form_submit_button("Apply", use_container_width=True)

# --- load data from view ------------------------------------------------------
def _load_groups() -> pd.DataFrame:
    if not _exists_view(V_TCL_OV):
        st.error(f"Required view {V_TCL_OV} not found."); st.stop()

    where, params = [], {}
    if not most_recent:
        where.append("cross_date::date BETWEEN :d1 AND :d2")
        params.update({"d1": d_from, "d2": d_to})

    if qtxt.strip():
        params["q"] = f"%{qtxt.strip()}%"
        where.append(
            """(
              treated_clutch_code          ILIKE :q OR
              clutch_code                  ILIKE :q OR
              cross_code                   ILIKE :q OR
              COALESCE(clutch_genotype,'')             ILIKE :q OR
              COALESCE(treatment_codes_rollup,'')      ILIKE :q OR
              COALESCE(treatment_names_rollup,'')      ILIKE :q OR
              COALESCE(treatment_fluors_rollup,'')     ILIKE :q OR
              COALESCE(genotype_fusions_rollup,'')     ILIKE :q OR
              COALESCE(mom_fish_code,'')               ILIKE :q OR
              COALESCE(dad_fish_code,'')               ILIKE :q OR
              COALESCE(mom_genotype,'')                ILIKE :q OR
              COALESCE(dad_genotype,'')                ILIKE :q
            )"""
        )

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    params["lim"] = int(lim)

    sql = text(
        f"""
        SELECT *
        FROM {V_TCL_OV}
        {where_sql}
        ORDER BY cross_date, clutch_code, group_created_at
        LIMIT :lim
        """
    )
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")

    return df

df = _load_groups()
st.caption(f"{len(df)} treated clutch group(s)")
if df.empty:
    st.info("No treated clutch groups with the current filters.")
    st.stop()

# --- main grid ----------------------------------------------------------------
cols = [
    "treated_clutch_code",
    "clutch_code",
    "cross_code",
    "cross_date",
    "clutch_birthday",
    "treatments_count_group",
    "treatment_fluors_rollup",
    "genotype_fusions_rollup",
    "treatment_vs_genotype_fusions",
]
grid_src = df[cols].copy()
if "✓ Select" not in grid_src.columns:
    grid_src.insert(0, "✓ Select", False)

st.subheader("Treated clutch groups")
grid = st.data_editor(
    grid_src,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select":                   st.column_config.CheckboxColumn("✓", default=False),
        "treated_clutch_code":        st.column_config.TextColumn("Group code", disabled=True),
        "clutch_code":                st.column_config.TextColumn("Clutch", disabled=True),
        "cross_code":                 st.column_config.TextColumn("Cross", disabled=True),
        "cross_date":                 st.column_config.DateColumn("Cross date", disabled=True),
        "clutch_birthday":           st.column_config.DateColumn("Clutch birthday", disabled=True),
        "treatments_count_group":     st.column_config.NumberColumn("# tx", disabled=True, format="%d"),
        "treatment_fluors_rollup":    st.column_config.TextColumn("Tx → fluors/dyes", disabled=True, width="large"),
        "genotype_fusions_rollup":    st.column_config.TextColumn("Genotype → fluors", disabled=True, width="large"),
        "treatment_vs_genotype_fusions": st.column_config.TextColumn("Tx vs genotype (fluors)", disabled=True, width="large"),
    },
    key="overview_treated_clutches_grid_v1",
)

sel_mask = grid.get("✓ Select", pd.Series(False, index=grid.index)).fillna(False).astype(bool)
picked = df[sel_mask].reset_index(drop=True)

# --- details ------------------------------------------------------------------
st.subheader("Details")
if picked.empty:
    st.info("Select a row above to view linked details.")
    st.stop()

if len(picked) > 1:
    st.warning("Multiple rows selected; showing the first one.")

row = picked.iloc[0].to_dict()

def _pivot(title: str, rows: List[Tuple[str, Any]]):
    dfp = pd.DataFrame(rows, columns=["Field", "Value"])
    st.subheader(title)
    st.dataframe(dfp, hide_index=True, use_container_width=True)

# Group summary: codes & comparison fields
summary_rows = [
    ("Group code",                row.get("treated_clutch_code")),
    ("Clutch code",               row.get("clutch_code")),
    ("Cross code",                row.get("cross_code")),
    ("Cross date",                row.get("cross_date")),
    ("Clutch birthday",           row.get("clutch_birthday")),
    ("# treatments",              row.get("treatments_count_group")),
    ("Tx codes",                  row.get("treatment_codes_rollup")),
    ("Genotype codes",            row.get("genotype_codes_rollup")),
    ("Tx codes > genotype codes", row.get("treatment_vs_genotype_codes")),
    ("Tx names",                  row.get("treatment_names_rollup")),
    ("Allele names",              row.get("allele_names_rollup")),
    ("Tx names > allele names",   row.get("treatment_vs_allele_names")),
    ("Tx → fluors/dyes",          row.get("treatment_fluors_rollup")),
    ("Genotype → fluors",         row.get("genotype_fusions_rollup")),
    ("Tx fluors > genotype",      row.get("treatment_vs_genotype_fusions")),
    ("Clutch genotype",           row.get("clutch_genotype_pretty")),
]

cA, cB = st.columns(2)
with cA:
    _pivot("Group summary", summary_rows)

# Parents summary: codes/genotypes/fusions
mom_rows = [
    ("Fish code",   row.get("mom_fish_code")),
    ("Genotype",    row.get("mom_genotype")),
    ("Fusions",     row.get("mom_fusions")),
]
dad_rows = [
    ("Fish code",   row.get("dad_fish_code")),
    ("Genotype",    row.get("dad_genotype")),
    ("Fusions",     row.get("dad_fusions")),
]

with cB:
    _pivot("Mother — profile", mom_rows)
    _pivot("Father — profile", dad_rows)

st.markdown("---")
st.info(
    "This view is driven entirely by public.v_treated_clutches_overview, "
    "including genotype rollups and the three comparison fields:\n"
    "- Tx fluors > genotype fluors\n"
    "- Tx codes  > genotype codes\n"
    "- Tx names  > allele names"
)