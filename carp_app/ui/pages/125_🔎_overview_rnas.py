# carp_app/ui/pages/125_🔎_overview_rnas.py
from __future__ import annotations

import os, sys, pathlib
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ---- repo wiring ------------------------------------------------------------
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

# ---- auth / page ------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🔎 Overview RNAs", page_icon="🧬", layout="wide")
st.title("🔎 Overview RNAs")

@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _engine()

def _normalize_q(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None

# ---- filters -----------------------------------------------------------------
with st.form("filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input("Search (code / name / nickname / notes / markers)", "")
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
    _ = st.form_submit_button("Apply", use_container_width=True)

q = _normalize_q(q_raw)

# ---- query v_constructs_overview (verified columns only) ---------------------
sql = text(
    """
    SELECT
      construct_code        AS rna_code,
      construct_name        AS name,
      construct_nickname    AS nickname,
      construct_notes       AS notes,
      fluors                AS fluor_names,
      tag_codes             AS tag_names,
      fusions               AS fusion_names,
      n_fusions,
      created_at
    FROM public.v_constructs_overview
    WHERE
      (:q IS NULL)
      OR COALESCE(construct_code, '')      ILIKE :ql
      OR COALESCE(construct_name, '')      ILIKE :ql
      OR COALESCE(construct_nickname, '')  ILIKE :ql
      OR COALESCE(construct_notes, '')     ILIKE :ql
      OR COALESCE(fluors, '')              ILIKE :ql
      OR COALESCE(tag_codes, '')           ILIKE :ql
      OR COALESCE(fusions, '')             ILIKE :ql
    ORDER BY created_at DESC NULLS LAST, construct_code
    LIMIT :lim
    """
)

params = {
    "q": q,
    "ql": f"%{q}%" if q else None,
    "lim": lim,
}

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

# normalize string columns
for c in df.select_dtypes(include=["object", "string"]).columns:
    df[c] = df[c].astype("string").fillna("")

st.caption(f"{len(df)} row(s)")

# ---- table -------------------------------------------------------------------
view_cols = [
    "rna_code",
    "name",
    "nickname",
    "fusion_names",
    "fluor_names",
    "tag_names",
    "n_fusions",
    "notes",
    "created_at",
]
for c in view_cols:
    if c not in df.columns:
        df[c] = "" if c not in ("n_fusions", "created_at") else (
            0 if c == "n_fusions" else pd.NaT
        )

st.data_editor(
    df[view_cols],
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "rna_code":     st.column_config.TextColumn("RNA code", disabled=True),
        "name":         st.column_config.TextColumn("Name", disabled=True),
        "nickname":     st.column_config.TextColumn("Nickname", disabled=True),
        "fusion_names": st.column_config.TextColumn("Fusion names", disabled=True),
        "fluor_names":  st.column_config.TextColumn("Fluor names", disabled=True),
        "tag_names":    st.column_config.TextColumn("Tag names", disabled=True),
        "n_fusions":    st.column_config.NumberColumn("# fusions", disabled=True),
        "notes":        st.column_config.TextColumn("Notes", disabled=True),
        "created_at":   st.column_config.DatetimeColumn("Created at", disabled=True),
    },
    key="rnas_overview_from_constructs",
)

# ---- CSV download ------------------------------------------------------------
st.download_button(
    "⬇︎ Download CSV",
    data=df[view_cols].to_csv(index=False).encode("utf-8"),
    file_name="overview_rnas_from_constructs.csv",
    type="secondary",
    use_container_width=True,
)