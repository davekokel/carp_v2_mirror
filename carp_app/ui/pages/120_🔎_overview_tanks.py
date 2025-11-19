# carp_app/ui/pages/120_🔎_overview_tanks.py
from __future__ import annotations

import os, sys, pathlib
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── repo root on sys.path ─────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.lib.app_ctx import get_engine as _create_engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

# ── auth & page setup ─────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview tanks",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview tanks")

# ── engine (cached) ───────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return _create_engine()

def _normalize_q(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None

# ── filters ───────────────────────────────────────────────────────────────────
with st.form("tank_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        q_raw = st.text_input(
            "Search (tank_code / fish_code / nickname / background / genotype / base_codes / fluors / notes)",
            "",
        )
    with c2:
        status = st.selectbox(
            "Status",
            options=["active", "inactive", "all"],
            index=0,
        )
    with c3:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=500,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

q = _normalize_q(q_raw)

# ── query v_tanks_overview + fish_instance ────────────────────────────────────
sql = text(
    """
    SELECT
      t.id                AS tank_id,
      t.tank_code,
      t.fish_code,
      f.nickname,
      f.birthday,
      f.genetic_background,
      f.line_building_stage,
      t.genotype_pretty,
      t.genotype_alleles_pretty,
      t.genotype_alleles_priority_pretty,
      t.genotype_base_codes,
      t.genotype_fluors,
      t.treatment_base_codes,
      t.treatment_rna_codes,
      t.treatment_fluors,
      t.all_base_codes,
      t.all_fluors,
      t.status,
      t.location,
      t.volume_l,
      t.role,
      t.since_days,
      t.started_at,
      t.ended_at,
      t.created,
      t.tank_notes
    FROM public.v_tanks_overview t
    LEFT JOIN public.fish_instance f
      ON f.id = t.fish_id
    WHERE
      (:status = 'all' OR t.status = :status)
      AND (
        :q IS NULL
        OR COALESCE(t.tank_code, '')              ILIKE :ql
        OR COALESCE(t.fish_code, '')              ILIKE :ql
        OR COALESCE(f.nickname, '')               ILIKE :ql
        OR COALESCE(f.genetic_background, '')     ILIKE :ql
        OR COALESCE(t.genotype_pretty, '')        ILIKE :ql
        OR COALESCE(t.genotype_base_codes, '')    ILIKE :ql
        OR COALESCE(t.genotype_fluors, '')        ILIKE :ql
        OR COALESCE(t.all_base_codes, '')         ILIKE :ql
        OR COALESCE(t.all_fluors, '')             ILIKE :ql
        OR COALESCE(t.tank_notes, '')             ILIKE :ql
      )
    ORDER BY t.status, t.tank_code
    LIMIT :lim
    """
)

params = {
    "q": q,
    "ql": f"%{q}%" if q else None,
    "status": status,
    "lim": lim,
}

with engine().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} match(es)")

# ── main table ────────────────────────────────────────────────────────────────
if df.empty:
    st.info("No rows match your filters.")
else:
    preferred_cols = [
        "tank_code",
        "fish_code",
        "nickname",
        "genetic_background",
        "birthday",
        "line_building_stage",
        "genotype_pretty",
        "genotype_alleles_pretty",
        "genotype_alleles_priority_pretty",
        "genotype_base_codes",
        "genotype_fluors",
        "treatment_base_codes",
        "treatment_rna_codes",
        "treatment_fluors",
        "all_base_codes",
        "all_fluors",
        "status",
        "location",
        "volume_l",
        "role",
        "since_days",
        "started_at",
        "ended_at",
        "created",
        "tank_notes",
    ]
    cols = [c for c in preferred_cols if c in df.columns] + [
        c for c in df.columns if c not in preferred_cols
    ]
    df = df[cols]

    st.data_editor(
        df,
        key="tanks_overview",
        use_container_width=True,
        hide_index=True,
        column_config={
            "tank_code":          st.column_config.TextColumn("Tank code"),
            "fish_code":          st.column_config.TextColumn("Fish code"),
            "nickname":           st.column_config.TextColumn("Nickname"),
            "genetic_background": st.column_config.TextColumn("Background"),
            "birthday":           st.column_config.DateColumn("Birthday"),
            "line_building_stage": st.column_config.TextColumn("Line stage"),
            "genotype_pretty":    st.column_config.TextColumn("Genotype (pretty)"),
            "genotype_alleles_pretty": st.column_config.TextColumn("Alleles (pretty)"),
            "genotype_alleles_priority_pretty": st.column_config.TextColumn("Alleles (priority pretty)"),
            "genotype_base_codes": st.column_config.TextColumn("Genotype base codes"),
            "genotype_fluors":    st.column_config.TextColumn("Genotype fluors"),
            "treatment_base_codes": st.column_config.TextColumn("Treatment base codes"),
            "treatment_rna_codes":  st.column_config.TextColumn("Treatment RNA codes"),
            "treatment_fluors":   st.column_config.TextColumn("Treatment fluors"),
            "all_base_codes":     st.column_config.TextColumn("All base codes"),
            "all_fluors":         st.column_config.TextColumn("All fluors"),
            "status":             st.column_config.TextColumn("Status"),
            "location":           st.column_config.TextColumn("Location"),
            "volume_l":           st.column_config.NumberColumn("Volume (L)"),
            "role":               st.column_config.TextColumn("Role"),
            "since_days":         st.column_config.NumberColumn("Since (days)"),
            "started_at":         st.column_config.DatetimeColumn("Started at"),
            "ended_at":           st.column_config.DatetimeColumn("Ended at"),
            "created":            st.column_config.DatetimeColumn("Tank created"),
            "tank_notes":         st.column_config.TextColumn("Tank notes"),
        },
    )

# ── debug ─────────────────────────────────────────────────────────────────────
with st.expander("Debug", expanded=False):
    st.write("Preview of raw data frame:")
    st.dataframe(df.head(50), use_container_width=True)