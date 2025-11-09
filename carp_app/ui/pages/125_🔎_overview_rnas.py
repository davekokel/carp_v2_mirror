# carp_app/ui/pages/125_🔎_overview_rnas.py
from __future__ import annotations

import os, sys, pathlib
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

st.set_page_config(page_title="CARP — Overview RNAs", page_icon="🔎", layout="wide")
st.title("🔎 Overview RNAs")

@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL","")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _engine()

with _eng().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

with st.form("filters"):
    c1, c2 = st.columns([3,1])
    q = c1.text_input("Search (rna_code / base plasmid / name / fusions / fluors / tags)")
    limit = int(c2.number_input("Limit", min_value=10, max_value=5000, value=500, step=100))
    st.form_submit_button("Apply", use_container_width=True)

sql = text("""
  SELECT
    rna_code,
    COALESCE(rna_name,'')           AS rna_name,
    base_plasmid_code,
    COALESCE(base_plasmid_name,'')  AS base_plasmid_name,
    COALESCE(genetic_element,'')    AS genetic_element,
    COALESCE(fusion_names,'')       AS fusion_names,
    COALESCE(fluor_names,'')        AS fluor_names,
    COALESCE(tag_names,'')          AS tag_names,
    COALESCE(notes,'')              AS notes,
    created_by,
    created_at
  FROM public.v_rnas
  WHERE (:q IS NULL)
     OR rna_code ILIKE :ql
     OR base_plasmid_code ILIKE :ql
     OR COALESCE(rna_name,'') ILIKE :ql
     OR COALESCE(base_plasmid_name,'') ILIKE :ql
     OR COALESCE(fusion_names,'') ILIKE :ql
     OR COALESCE(fluor_names,'') ILIKE :ql
     OR COALESCE(tag_names,'') ILIKE :ql
     OR COALESCE(notes,'') ILIKE :ql
  ORDER BY created_at DESC NULLS LAST, rna_code
  LIMIT :lim
""")
params = {"q": (q if (q or "").strip() else None), "ql": f"%{(q or '').strip()}%", "lim": int(limit)}

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} row(s)")
if df.empty:
    st.info("No RNAs found.")
else:
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "rna_code":           st.column_config.TextColumn("RNA code", disabled=True),
            "rna_name":           st.column_config.TextColumn("Name", disabled=True),
            "base_plasmid_code":  st.column_config.TextColumn("Base plasmid", disabled=True),
            "base_plasmid_name":  st.column_config.TextColumn("Plasmid name", disabled=True),
            "genetic_element":    st.column_config.TextColumn("Element", disabled=True),
            "fusion_names":       st.column_config.TextColumn("Fusions", disabled=True),
            "fluor_names":        st.column_config.TextColumn("Fluors", disabled=True),
            "tag_names":          st.column_config.TextColumn("Tags", disabled=True),
            "notes":              st.column_config.TextColumn("Notes", disabled=True),
            "created_by":         st.column_config.TextColumn("Created by", disabled=True),
            "created_at":         st.column_config.DatetimeColumn("Created at", disabled=True),
        },
        key="rnas_overview_v1",
    )
    st.download_button(
        "⬇︎ Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="rnas_overview.csv",
        type="secondary"
    )