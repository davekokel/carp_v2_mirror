# carp_app/ui/pages/100_🧪_overview_constructs_v10.py
from __future__ import annotations

import os
import pathlib
import sys
from typing import Dict, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── path / auth bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine as _create_engine


sb, session, user = require_auth()
require_email_otp()

st.set_page_config(
    page_title="CARP — v10 Constructs Overview",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 v10 Constructs Overview")


@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return _create_engine()


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


# ───────── filters ─────────
with st.form("construct_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 1.3, 0.8])
    with c1:
        q_raw = st.text_input(
            "Search (code / name / kind / resistance / fluors / tags / organelles)",
            "",
        )
    with c2:
        kind_choice = st.selectbox(
            "Kind contains…",
            ["(any)", "plasmid", "rna", "crispr"],
            index=0,
        )
    with c3:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=1000,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)
kind_token = kind_choice if kind_choice != "(any)" else None

where = ["1=1"]
params: Dict[str, object] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  construct_code ILIKE :ql"
        " OR construct_name ILIKE :ql"
        " OR COALESCE(construct_kind,'') ILIKE :ql"
        " OR COALESCE(resistance,'') ILIKE :ql"
        " OR COALESCE(fluor_codes,'') ILIKE :ql"
        " OR COALESCE(tag_codes,'') ILIKE :ql"
        " OR COALESCE(organelles,'') ILIKE :ql"
        ")"
    )

if kind_token:
    params["kind_like"] = f"%{kind_token}%"
    where.append("construct_kind ILIKE :kind_like")

where_sql = " AND ".join(where)

sql = text(
    f"""
    SELECT
      construct_code,
      construct_kind,
      construct_name,
      resistance,
      description,
      fluor_codes,
      tag_codes,
      organelles,
      fusion_pretty,
      fluor_organelle_codes,
      created_at
    FROM public.v10_constructs_overview
    WHERE {where_sql}
    ORDER BY created_at DESC NULLS LAST, construct_code
    LIMIT :lim
    """
)

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

if df.empty:
    st.info("No constructs match these filters.")
    st.stop()

# normalize display
for col in df.select_dtypes(include="object").columns:
    df[col] = df[col].fillna("")

st.caption(f"{len(df)} construct(s)")

view = df.copy()

st.data_editor(
    view,
    key="v10_constructs_overview",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "construct_code": st.column_config.TextColumn("construct_code", disabled=True),
        "construct_kind": st.column_config.TextColumn("kind", disabled=True),
        "construct_name": st.column_config.TextColumn("name", disabled=True, width="large"),
        "resistance": st.column_config.TextColumn("resistance", disabled=True),
        "description": st.column_config.TextColumn("description", disabled=True),
        "fluor_codes": st.column_config.TextColumn("fluor_codes", disabled=True),
        "tag_codes": st.column_config.TextColumn("tag_codes", disabled=True),
        "organelles": st.column_config.TextColumn("organelles", disabled=True),
        "fusion_pretty": st.column_config.TextColumn("fusion_pretty", disabled=True),
        "fluor_organelle_codes": st.column_config.TextColumn("fluor-organelle codes", disabled=True),
        "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
    },
)

st.download_button(
    "⬇︎ Download constructs (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="v10_constructs_overview.csv",
    type="secondary",
    mime="text/csv",
)