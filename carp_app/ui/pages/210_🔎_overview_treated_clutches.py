# carp_app/ui/pages/210_🧪_overview_treated_clutches.py
# 🔎 Overview — Treated clutches (v11, clutch_star-based)

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

V_CLUTCH_STAR = "public.v11_clutch_star"

# --- auth / page --------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🔎 Overview: Treated clutches (v11)",
    page_icon="🧪",
    layout="wide",
)
st.title("🔎 Overview — Treated clutches (v11)")

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

def _pivot(title: str, rows: List[Tuple[str, Any]]):
    dfp = pd.DataFrame(rows, columns=["Field", "Value"])
    st.markdown(f"**{title}**")
    st.dataframe(dfp, hide_index=True, use_container_width=True)

# --- filters ------------------------------------------------------------------
today = date.today()
with st.form("filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        d_from = st.date_input("From (clutch date)", value=today - timedelta(days=60))
    with c2:
        d_to = st.date_input("To (clutch date)", value=today + timedelta(days=7))
    with c3:
        who = st.text_input("Created by (ignored for now)", "")
    with c4:
        qtxt = st.text_input(
            "Search (clutch/genotype/treatments/fluors)",
            "",
        )
    c5, c6 = st.columns([1, 1])
    with c5:
        most_recent = st.checkbox("Most recent (ignore dates)", value=False)
    with c6:
        lim = st.number_input("Limit", min_value=1, max_value=1000, value=500, step=50)
    st.form_submit_button("Apply", use_container_width=True)

# --- load data from v11_clutch_star ------------------------------------------
def _load_clutches() -> pd.DataFrame:
    if not _exists_view(V_CLUTCH_STAR):
        st.error(f"Required view {V_CLUTCH_STAR} not found."); st.stop()

    where: list[str] = []
    params: dict[str, Any] = {}

    # only clutches that actually have treatments
    where.append("(COALESCE(treat_codes,'') <> '' OR COALESCE(treatment_code,'') <> '')")

    if not most_recent:
        where.append("clutch_date::date BETWEEN :d1 AND :d2")
        params.update({"d1": d_from, "d2": d_to})

    qnorm = (qtxt or "").strip()
    if qnorm:
        params["q"] = f"%{qnorm}%"
        where.append(
            """(
              COALESCE(clutch_code,'')                 ILIKE :q OR
              COALESCE(genotype_pretty,'')             ILIKE :q OR
              COALESCE(genotype_basecode_code,'')      ILIKE :q OR
              COALESCE(genotype_transgene_allele_code,'') ILIKE :q OR
              COALESCE(treatment_code,'')              ILIKE :q OR
              COALESCE(treat_codes,'')                 ILIKE :q OR
              COALESCE(all_fluor_tag_rollup,'')        ILIKE :q OR
              COALESCE(all_organelle_fluor_rollup,'')  ILIKE :q
            )"""
        )

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    params["lim"] = int(lim)

    sql = text(
        f"""
        SELECT *
        FROM {V_CLUTCH_STAR}
        {where_sql}
        ORDER BY clutch_date, clutch_code
        LIMIT :lim
        """
    )
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")

    return df

df = _load_clutches()
st.caption(f"{len(df)} treated clutch(es)")
if df.empty:
    st.info("No treated clutches with the current filters.")
    st.stop()

# --- main grid ----------------------------------------------------------------
cols = [
    "clutch_code",
    "clutch_date",
    "treatment_code",
    "treat_codes",
]
grid_src = df[cols].copy()
if "✓ Select" not in grid_src.columns:
    grid_src.insert(0, "✓ Select", False)

st.subheader("Treated clutches")
grid = st.data_editor(
    grid_src,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select":          st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code":       st.column_config.TextColumn("Clutch", disabled=True),
        "clutch_date":       st.column_config.DateColumn("Clutch date", disabled=True),
        "treatment_code":    st.column_config.TextColumn("Primary treatment", disabled=True),
        "treat_codes":       st.column_config.TextColumn("All treatment codes", disabled=True, width="large"),
    },
    key="overview_treated_clutches_grid_v11",
)

sel_mask = grid.get("✓ Select", pd.Series(False, index=grid.index)).fillna(False).astype(bool)
picked = df[sel_mask].reset_index(drop=True)

# --- details ------------------------------------------------------------------
st.subheader("Details")
if picked.empty:
    st.info("Select a row above to view clutch details.")
    st.stop()

if len(picked) > 1:
    st.warning("Multiple rows selected; showing the first one.")

row = picked.iloc[0].to_dict()

summary_rows = [
    ("Clutch id",             row.get("clutch_id")),
    ("Clutch code",           row.get("clutch_code")),
    ("Clutch date",           row.get("clutch_date")),
    ("Cross",                 row.get("cross_run_code") or row.get("cross_code")),
    ("Treatment code",        row.get("treatment_code")),
    ("All treatment codes",   row.get("treat_codes")),
    ("Genotype (pretty)",     row.get("genotype_pretty")),
    ("Genotype basecodes",    row.get("genotype_basecode_code")),
    ("Genotype allele codes", row.get("genotype_transgene_allele_code")),
    ("Treatments > transgenes", row.get("treatments_and_transgenes")),
    ("Tx → fluor::tag(pos)",  row.get("all_fluor_tag_rollup")),
    ("Tx → organelle-fluor",  row.get("all_organelle_fluor_rollup")),
]

_pivot("Clutch summary", summary_rows)

st.markdown("---")
st.info(
    "This v11 view is driven entirely by public.v11_clutch_star. "
    "Each row represents a clutch with at least one attached treatment, "
    "using the standard genotype and treatment rollup fields."
)