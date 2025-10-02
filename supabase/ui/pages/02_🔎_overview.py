# supabase/ui/pages/02_🔎_overview.py
from __future__ import annotations

# 🔒 require password on every page
try:
    from supabase.ui.auth_gate import require_app_unlock  # deployed/mirror path
except Exception:
    from auth_gate import require_app_unlock  # local path fallback
require_app_unlock()

import os
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

PAGE_TITLE = "CARP — Overview"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🔎", layout="wide")
st.title("🔎 Overview")
st.caption("Global search across fish, genotype, and treatments (via `public.vw_fish_overview`).")

# ------------------------- DB helpers (reuse style from upload page) -------------------------
def _ensure_sslmode(url: str) -> str:
    u = urlparse(url)
    host = (u.hostname or "").lower() if u.hostname else ""
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    if host in {"localhost", "127.0.0.1", "::1"}:
        q["sslmode"] = "disable"
    else:
        q.setdefault("sslmode", "require")
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))

def build_db_url() -> str:
    raw = (st.secrets.get("DB_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        # fallback from PG* if present
        required = ["PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError("No DB_URL/DATABASE_URL and missing PG* env vars: " + ", ".join(missing))
        raw = (
            "postgresql://"
            f"{os.getenv('PGUSER')}:{os.getenv('PGPASSWORD')}"
            f"@{os.getenv('PGHOST')}:{os.getenv('PGPORT')}/{os.getenv('PGDATABASE')}"
        )
    return _ensure_sslmode(raw)

def _mask_url_password(url: str) -> str:
    try:
        u = urlparse(url)
        netloc = u.netloc
        if "@" in netloc:
            creds, host = netloc.split("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                netloc = f"{user}:***@{host}"
        return u._replace(netloc=netloc).geturl()
    except Exception:
        return "(unavailable)"

@st.cache_resource(show_spinner=False)
def _engine():
    return create_engine(build_db_url(), pool_pre_ping=True, future=True, connect_args={"prepare_threshold": None})

# ------------------------- UI controls -------------------------
q = st.text_input("Search", placeholder="name, nickname, strain, genotype, RNA/plasmid notes…")
col_a, col_b, col_c = st.columns([1,1,2])
with col_a:
    page_size = st.selectbox("Rows per page", [25, 50, 100], index=1)
with col_b:
    page = st.number_input("Page", min_value=1, value=1, step=1)
offset = (page - 1) * page_size

# Optional quick filters (extend as needed)
with st.expander("Filters", expanded=False):
    stage = st.selectbox("Line building stage", ["(any)","founder","F0","F1","F2","F3","unknown"], index=0)
    strain = st.text_input("Strain contains")

# ------------------------- Build SQL -------------------------
where_clauses: List[str] = []
params: Dict[str, Any] = {}

if q:
    params["q"] = f"%{q}%"
    where_clauses.append(
        "("
        " fish_name ILIKE :q OR nickname ILIKE :q OR strain ILIKE :q "
        " OR genotype_text ILIKE :q OR rna_injections_text ILIKE :q OR plasmid_injections_text ILIKE :q "
        ")"
    )

if stage and stage != "(any)":
    params["stage"] = stage
    where_clauses.append("line_building_stage = :stage")

if strain:
    params["strain_like"] = f"%{strain}%"
    where_clauses.append("strain ILIKE :strain_like")

where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

# count + page query
SQL_COUNT = text(f"SELECT COUNT(*) FROM public.vw_fish_overview {where_sql}")
SQL_PAGE = text(
    f"""
    SELECT *
    FROM public.vw_fish_overview
    {where_sql}
    ORDER BY fish_name NULLS LAST
    LIMIT :limit OFFSET :offset
    """
)

params_page = dict(params)
params_page["limit"] = int(page_size)
params_page["offset"] = int(offset)

# ------------------------- Query + render -------------------------
try:
    with _engine().connect() as cx:
        total = cx.execute(SQL_COUNT, params).scalar() or 0
        rows = pd.read_sql(SQL_PAGE, cx, params=params_page)
except Exception as e:
    st.error(f"Query failed: {e}")
    st.stop()

left, right = st.columns([3,1])
with left:
    st.write(f"**{total}** matching rows")
with right:
    if not rows.empty:
        csv = rows.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, file_name=f"fish_overview_{datetime.utcnow().date()}.csv", mime="text/csv")

st.dataframe(rows, use_container_width=True, height=520)

with st.expander("Connection (masked)", expanded=False):
    try:
        st.code(_mask_url_password(build_db_url()))
    except Exception as e:
        st.caption(str(e))