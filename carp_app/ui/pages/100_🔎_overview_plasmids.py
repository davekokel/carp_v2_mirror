# carp_app/ui/pages/100_🔎_overview_plasmids.py
from __future__ import annotations

import os
import pathlib
import sys
from typing import Optional, Dict, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── repo bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock():
        ...
from carp_app.ui.lib.app_ctx import get_engine


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Constructs Overview",
    page_icon="🧪",
    layout="wide",
)
st.title("🧪 Constructs Overview")


# ───────── engine (cached) ─────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return get_engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── filters ─────────
with st.form("construct_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 1.5, 0.8])
    with c1:
        q_raw = st.text_input(
            "Search (code / nickname / name / type / fluors / tags / fusions)",
            "",
        )
    with c2:
        kind_choice = st.selectbox(
            "Construct kind",
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


# ───────── query v_constructs_overview ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  code            ILIKE :ql"
        " OR nickname        ILIKE :ql"
        " OR name            ILIKE :ql"
        " OR construct_kind  ILIKE :ql"
        " OR construct_type  ILIKE :ql"
        " OR fluors          ILIKE :ql"
        " OR tag_codes       ILIKE :ql"
        " OR fusions         ILIKE :ql"
        ")"
    )

if kind_filter:
    params["kind"] = kind_filter
    where.append("construct_kind = :kind")

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      code,
      construct_kind,
      construct_type,
      nickname,
      name,
      fluors,
      tag_codes,
      fusions,
      n_fusions,
      created_at
    FROM public.v_constructs_overview
    WHERE {where_sql}
    ORDER BY created_at DESC NULLS LAST, code
    LIMIT :lim
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

# let pandas handle NULLs
df = df.fillna("")
st.caption(f"{len(df)} construct(s)")


# ───────── table ─────────
view = df.copy()
view.insert(0, "✓ Select", False)

st.data_editor(
    view,
    key="constructs_overview_v9",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "code",
        "construct_kind",
        "construct_type",
        "nickname",
        "name",
        "fluors",
        "tag_codes",
        "fusions",
        "n_fusions",
        "created_at",
    ],
    column_config={
        "✓ Select":        st.column_config.CheckboxColumn("✓", default=False),
        "code":            st.column_config.TextColumn("Code", disabled=True),
        "construct_kind":  st.column_config.TextColumn("Kind", disabled=True),
        "construct_type":  st.column_config.TextColumn("Subtype", disabled=True),
        "nickname":        st.column_config.TextColumn("Nickname", disabled=True),
        "name":            st.column_config.TextColumn("Name", disabled=True),
        "fluors":          st.column_config.TextColumn("Fluors", disabled=True),
        "tag_codes":       st.column_config.TextColumn("Tags", disabled=True),
        "fusions":         st.column_config.TextColumn("Fusions", disabled=True),
        "n_fusions":       st.column_config.NumberColumn("n fusions", disabled=True),
        "created_at":      st.column_config.DatetimeColumn("Created", disabled=True),
    },
)

# ───────── export ─────────
st.download_button(
    "⬇︎ Download full constructs table (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="constructs_overview.csv",
    type="secondary",
    mime="text/csv",
)