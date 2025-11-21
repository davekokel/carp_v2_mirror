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

from carp_app.ui.lib.app_ctx import get_engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock():
        ...

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview tanks",
    page_icon="🔍",
    layout="wide",
)
st.title("🔍 Overview tanks")

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
with st.form("tank_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 1, 0.7])
    with c1:
        q_raw = st.text_input(
            "Search (tank_code / fish_code / status)",
            "",
        )
    with c2:
        status_choice = st.selectbox(
            "Status",
            ["all", "active", "retired"],
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

q = _norm(q_raw)
status_filter = status_choice if status_choice != "all" else None

# ───────── query v_tanks_overview ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  tank_code ILIKE :ql"
        " OR fish_code ILIKE :ql"
        " OR COALESCE(status,'') ILIKE :ql"
        ")"
    )

if status_filter:
    params["status"] = status_filter
    where.append("status = :status")

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      tank_id,
      tank_code,
      fish_code,
      status,
      created_at
    FROM public.v_tanks_overview
    WHERE {where_sql}
    ORDER BY created_at DESC, tank_code
    LIMIT :lim
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

df = df.fillna("")
st.caption(f"{len(df)} tank(s)")


# ───────── table ─────────
view = df.copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    key="tanks_overview_v8",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "tank_code",
        "fish_code",
        "status",
        "created_at",
    ],
    column_config={
        "✓ Select":   st.column_config.CheckboxColumn("✓", default=False),
        "tank_code":  st.column_config.TextColumn("Tank code", disabled=True),
        "fish_code":  st.column_config.TextColumn("Fish code", disabled=True),
        "status":     st.column_config.TextColumn("Status", disabled=True),
        "created_at": st.column_config.DatetimeColumn("Created at", disabled=True),
    },
)

# ───────── export ─────────
st.download_button(
    "⬇︎ Download tanks overview (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="tanks_overview.csv",
    type="secondary",
    mime="text/csv",
)
