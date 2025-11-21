from __future__ import annotations

import os
import sys
import pathlib
from datetime import datetime, date
from typing import Optional, Dict, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine as _engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Cross & Clutch Instances",
    page_icon="🧬",
    layout="wide",
)
st.title("🧬 Cross & Clutch Instances")

def eng() -> Engine:
    return _engine()

def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None

with st.form("cross_clutch_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.3, 1.3, 0.7])
    with c1:
        q_raw = st.text_input(
            "Search (TP-000001, FISH-2025-0001, tank code, cross code, clutch code, fish)",
            "",
        )
    with c2:
        from_raw = st.text_input("From clutch_date (YYYY-MM-DD)", "")
    with c3:
        to_raw = st.text_input("To clutch_date (YYYY-MM-DD)", "")
    with c4:
        lim = int(
            st.number_input(
                "Limit",
                min_value=10,
                max_value=2000,
                value=200,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)
from_date: Optional[date] = None
to_date: Optional[date] = None

if from_raw:
    try:
        from_date = datetime.strptime(from_raw, "%Y-%m-%d").date()
    except ValueError:
        st.warning("From date must be YYYY-MM-DD if provided.")
        st.stop()

if to_raw:
    try:
        to_date = datetime.strptime(to_raw, "%Y-%m-%d").date()
    except ValueError:
        st.warning("To date must be YYYY-MM-DD if provided.")
        st.stop()

where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  COALESCE(clutch_code,'')        ILIKE :ql"
        " OR COALESCE(clutch_label,'')     ILIKE :ql"
        " OR COALESCE(cross_label,'')      ILIKE :ql"
        " OR COALESCE(cross_id::text,'')   ILIKE :ql"
        " OR COALESCE(cross_date::text,'') ILIKE :ql"
        " OR COALESCE(female_fish_code,'') ILIKE :ql"
        " OR COALESCE(male_fish_code,'')   ILIKE :ql"
        " OR COALESCE(notes,'')            ILIKE :ql"
        ")"
    )

if from_date:
    params["from_d"] = from_date.isoformat()
    where.append("clutch_date >= :from_d")

if to_date:
    params["to_d"] = to_date.isoformat()
    where.append("clutch_date <= :to_d")

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      clutch_id,
      clutch_code,
      clutch_label,
      clutch_date,
      estimated_egg_count,
      cross_id,
      cross_date,
      cross_label,
      expected_genotype_code,
      female_fish_code,
      male_fish_code,
      notes,
      source_system,
      import_batch_id,
      created_at
    FROM public.v_clutches_overview
    WHERE {where_sql}
    ORDER BY cross_date DESC NULLS LAST,
             clutch_date DESC NULLS LAST,
             created_at DESC NULLS LAST
    LIMIT :lim
""")

with eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

df = df.fillna("")
st.caption(f"{len(df)} clutch instance(s) / cross row(s)")

if df.empty:
    st.info("No clutches / crosses match the current filters.")
else:
    st.data_editor(
        df,
        key="crosses_clutches_overview_v8",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "clutch_id":             st.column_config.TextColumn("Clutch id", disabled=True),
            "clutch_code":           st.column_config.TextColumn("Clutch code (raw)", disabled=True),
            "clutch_label":          st.column_config.TextColumn("Clutch label", disabled=True),
            "clutch_date":           st.column_config.DateColumn("Clutch date", disabled=True),
            "estimated_egg_count":   st.column_config.NumberColumn("Est. eggs", disabled=True),
            "cross_id":              st.column_config.TextColumn("Cross id", disabled=True),
            "cross_date":            st.column_config.DateColumn("Cross date", disabled=True),
            "cross_label":           st.column_config.TextColumn("Cross label", disabled=True),
            "expected_genotype_code": st.column_config.TextColumn("Expected genotype", disabled=True),
            "female_fish_code":      st.column_config.TextColumn("Mother fish", disabled=True),
            "male_fish_code":        st.column_config.TextColumn("Father fish", disabled=True),
            "notes":                 st.column_config.TextColumn("Notes", disabled=True),
            "source_system":         st.column_config.TextColumn("Source", disabled=True),
            "import_batch_id":       st.column_config.TextColumn("Batch", disabled=True),
            "created_at":            st.column_config.DatetimeColumn("Created at", disabled=True),
        },
    )

    st.download_button(
        "⬇︎ Download cross & clutch rows (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="crosses_clutches_overview.csv",
        type="secondary",
        mime="text/csv",
    )
