# carp_app/ui/pages/125_🔎_overview_rnas.py
from __future__ import annotations

import os, sys, pathlib
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo wiring
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

# ── Auth / page ──────────────────────────────────────────────────────────────
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

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2 = st.columns([3,1])
    with c1:
        q = st.text_input("Search (code/name/base/markers/notes)", "")
    with c2:
        limit = int(st.number_input("Limit", min_value=50, max_value=5000, value=500, step=50))
    st.form_submit_button("Apply", use_container_width=True)

# Pull whatever the view exposes; normalize columns in Python
sql = text("""
  SELECT * FROM public.v_rnas
  ORDER BY created_at DESC NULLS LAST, rna_code
  LIMIT :lim
""")
with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params={"lim": int(limit)})

# Apply text filter client-side (avoids guessing DB columns)
def _contains(s: pd.Series, needle: str) -> pd.Series:
    return s.fillna("").astype(str).str.contains(needle, case=False, na=False)

if q.strip():
    needle = q.strip()
    cols_for_filter = [c for c in df.columns if df[c].dtype == object or str(df[c].dtype).startswith(("string","object"))]
    if cols_for_filter:
        mask = pd.Series(False, index=df.index)
        for c in cols_for_filter:
            mask |= _contains(df[c], needle)
        df = df.loc[mask].copy()

# Ensure friendly columns exist even if the view doesn’t have them
must_have = [
    "rna_code",
    "rna_name",
    "base_plasmid_code",   # code only (no name expected in your model)
    "fusion_names",        # may be missing in current view → synthesize empty
    "fluor_names",
    "tag_names",
    "notes",
    "created_by",
    "created_at",
]
for c in must_have:
    if c not in df.columns:
        # create empty columns for missing optional fields
        df[c] = "" if c not in ("created_at",) else pd.NaT

# Reorder for display (drop columns not recognized to the end)
display_cols = [c for c in must_have if c in df.columns]
extras = [c for c in df.columns if c not in display_cols]
df = df[display_cols + extras]

st.caption(f"{len(df)} row(s)")
st.dataframe(df, width="stretch", hide_index=True)

st.download_button(
    "⬇︎ Download CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="overview_rnas.csv",
    type="secondary",
    use_container_width=True,
)