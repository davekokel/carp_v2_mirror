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
# Robust import for cloud runners
t# Ensure repo root (parent of 'supabase') is first on sys.path before importing local package
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]  # .../carp_v2_mirror
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase.queries import load_fish_overview

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

PAGE_TITLE = "CARP — Overview"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🔎", layout="wide")
st.title("🔎 Overview")
st.caption("Global search across fish, genotype, and treatments (via `public.vw_fish_overview_with_label`).")

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

# Optional quick filters (extend as needed)
with st.expander("Filters", expanded=False):
    stage = st.selectbox("Line building stage", ["(any)","founder","F0","F1","F2","F3","unknown"], index=0)
    strain = st.text_input("Strain contains")

# ------------------------- Infinite scroll state -------------------------
if "overview_offset" not in st.session_state:
    st.session_state.overview_offset = 0
if "overview_page_size" not in st.session_state:
    st.session_state.overview_page_size = 100  # change as needed

# optional reset button
if st.button("🔄 Reset results"):
    st.session_state.overview_offset = 0

# compute page based on offset
page = (st.session_state.overview_offset // st.session_state.overview_page_size) + 1

# ------------------------- Load data -------------------------
try:
    total, rows = load_fish_overview(
        _engine(),
        page_size=st.session_state.overview_page_size,
        page=page,
        q=q,
        stage=stage,
        strain=strain
    )
except Exception as e:
    st.error(f"Query failed: {e}")
    st.stop()

# ------------------------- Display -------------------------
# Prefer enriched creator if present
if "created_by_enriched" in rows.columns:
    if "created_by" in rows.columns:
        # Treat empty strings as missing, then prefer enriched
        cb = rows["created_by"].astype("string")
        cb = cb.mask(cb.str.strip() == "")
        rows["created_by"] = cb.combine_first(rows["created_by_enriched"])
    else:
        rows["created_by"] = rows["created_by_enriched"]
# Prefer filled transgene columns if provided by the view
for orig, filled in [
    ("transgene_base_code", "transgene_base_code_filled"),
    ("allele_number", "allele_number_filled"),
    ("transgene_name", "transgene_name_filled"),
]:
    if filled in rows.columns:
        if orig in rows.columns:
            s = rows[orig].astype("string")
            rows[orig] = s.mask(s.str.strip() == "").combine_first(rows[filled])
        else:
            rows[orig] = rows[filled]
# Deduplicate any repeated 'batch_label' columns (e.g., from v.* plus batch_label)
# Deduplicate 'transgene_*' columns if they appear twice (from v.* plus filled)
for col in ["transgene_base_code", "allele_number", "transgene_name"]:
    dups = [i for i, c in enumerate(rows.columns) if c == col]
    if len(dups) > 1:
        coalesced = rows.iloc[:, dups].bfill(axis=1).iloc[:, 0]
        rows = rows.drop(columns=[rows.columns[i] for i in dups[1:]])
        rows[col] = coalesced
dup_idx = [i for i, c in enumerate(rows.columns) if c == "batch_label"]
if len(dup_idx) > 1:
    coalesced = rows.iloc[:, dup_idx].bfill(axis=1).iloc[:, 0]
    rows = rows.drop(columns=[rows.columns[i] for i in dup_idx[1:]])
    rows["batch_label"] = coalesced
# Optional: filter by batch label when present
if "batch_label" in rows.columns:
    s = rows["batch_label"].astype("string")
    label_opts = sorted(pd.unique(s.dropna()))
    if label_opts:
        selected_labels = st.multiselect("Batch label", options=label_opts, key="batch_label_filter")
        if selected_labels:
            rows = rows[s.isin(selected_labels)]
_total_after = len(rows)
st.caption(f"Showing {min(st.session_state.overview_offset + st.session_state.overview_page_size, _total_after):,} of {_total_after:,} rows")

preferred_order = [
    "batch_label",
    "fish_code", "fish_name", "nickname", "line_building_stage", "created_by", "date_of_birth",
    "transgene_base_code_filled", "allele_number_filled", "allele_code_filled", "allele_name_filled",
    "transgene_pretty_filled", "transgene_pretty_nickname",  # ← add these if you want both
    "injected_plasmid_name", "injected_rna_name",
]
available_cols = [col for col in preferred_order if col in rows.columns]
display_df = rows[available_cols].copy()
if "batch_label" not in rows.columns:
    st.info("`batch_label` isn’t present in the current query results. Showing other columns until it’s wired up in the backend view.")

st.dataframe(display_df, use_container_width=True)

# “Load more” button
if st.session_state.overview_offset + st.session_state.overview_page_size < total:
    if st.button("⬇️ Load more"):
        st.session_state.overview_offset += st.session_state.overview_page_size
        st.rerun()


