from __future__ import annotations

import os
import pathlib
import sys

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

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


def _norm(s: str | None) -> str:
    s = (s or "").strip()
    return s


with st.form("construct_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 1.5, 0.8])
    with c1:
        q_raw = st.text_input(
            "Search (code / name / kind / resistance)",
            "",
        )
    with c2:
        kind_choice = st.selectbox(
            "Kind",
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
kind_filter = kind_choice if kind_choice != "(any)" else None

where = ["1=1"]
params: dict[str, object] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  construct_code ILIKE :ql"
        " OR construct_name ILIKE :ql"
        " OR COALESCE(construct_kind,'') ILIKE :ql"
        " OR COALESCE(resistance,'') ILIKE :ql"
        ")"
    )

if kind_filter:
    params["kind"] = kind_filter
    where.append("construct_kind = :kind")

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      construct_code,
      construct_kind,
      construct_name,
      resistance,
      description,
      created_at
    FROM public.v10_constructs_overview
    WHERE {where_sql}
    ORDER BY created_at DESC NULLS LAST, construct_code
    LIMIT :lim
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

df = df.fillna("")
st.caption(f"{len(df)} construct(s)")

view = df.copy()
st.data_editor(
    view,
    key="v10_constructs_overview",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
)

st.download_button(
    "⬇︎ Download constructs (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="v10_constructs_overview.csv",
    type="secondary",
    mime="text/csv",
)