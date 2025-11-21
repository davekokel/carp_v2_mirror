# carp_app/ui/pages/110_🔎_overview_fish.py
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
    page_title="CARP — Overview Fish",
    page_icon="🐟",
    layout="wide",
)
st.title("🐟 Overview fish")

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
with st.form("fish_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Search (code / nickname / background / genotype / base codes)",
            "",
        )
    with c2:
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

q = _norm(q_raw)

# ───────── query v_fish_overview ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  fish_code                        ILIKE :ql"
        " OR COALESCE(nickname,'')         ILIKE :ql"
        " OR COALESCE(genetic_background,'') ILIKE :ql"
        " OR COALESCE(genotype_pretty,'')     ILIKE :ql"
        " OR COALESCE(genotype_alleles_pretty,'') ILIKE :ql"
        " OR COALESCE(genotype_base_codes,'')     ILIKE :ql"
        ")"
    )

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      id,
      fish_code,
      nickname,
      genetic_background,
      birthday,
      created_at,
      genotype_base_codes,
      genotype_alleles_pretty,
      genotype_pretty,
      genotype_source
    FROM public.v_fish_overview
    WHERE {where_sql}
    ORDER BY created_at DESC NULLS LAST, fish_code
    LIMIT :lim
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

for c in df.select_dtypes(include=["object", "string"]).columns:
    df[c] = df[c].astype("string").fillna("")

st.caption(f"{len(df)} fish")


# ───────── main table ─────────
view = df.copy()
view.insert(0, "✓ Select", False)

fish_grid = st.data_editor(
    view,
    key="fish_overview_v8",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "fish_code",
        "nickname",
        "genetic_background",
        "birthday",
        "genotype_pretty",
        "genotype_base_codes",
        "genotype_alleles_pretty",
        "genotype_source",
        "created_at",
    ],
    column_config={
        "✓ Select":             st.column_config.CheckboxColumn("✓", default=False),
        "fish_code":            st.column_config.TextColumn("Fish code", disabled=True),
        "nickname":             st.column_config.TextColumn("Nickname", disabled=True),
        "genetic_background":   st.column_config.TextColumn("Background", disabled=True),
        "birthday":             st.column_config.DateColumn("Birthday", disabled=True),
        "genotype_pretty":      st.column_config.TextColumn("Genotype (pretty)", disabled=True),
        "genotype_base_codes":  st.column_config.TextColumn("Genotype base codes", disabled=True),
        "genotype_alleles_pretty": st.column_config.TextColumn("Alleles (pretty)", disabled=True),
        "genotype_source":      st.column_config.TextColumn("Genotype source", disabled=True),
        "created_at":           st.column_config.DatetimeColumn("Created at", disabled=True),
    },
)

# ───────── export ─────────
st.download_button(
    "⬇︎ Download fish overview (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="fish_overview.csv",
    type="secondary",
    mime="text/csv",
)
