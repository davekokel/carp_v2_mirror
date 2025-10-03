# supabase/ui/pages/20_add_treatments.py
from __future__ import annotations

# 🔒 lock page
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os, hashlib, importlib, sys
from datetime import datetime
from typing import Optional
from pathlib import Path

import streamlit as st
from sqlalchemy import create_engine

# --- repo import path shim ---
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import supabase.queries as _queries
importlib.reload(_queries)
from supabase import queries as Q

PAGE_TITLE = "CARP — Add Treatments"
st.set_page_config(page_title=PAGE_TITLE, page_icon="💊")
st.title("💊 Add Treatments to Existing Fish")

# --- DB bootstrap ---
DB_URL = os.environ.get("DB_URL")
if not DB_URL:
    st.error("DB_URL is not set in the environment.")
    st.stop()

engine = create_engine(DB_URL)
DBKEY = hashlib.md5(DB_URL.encode()).hexdigest()[:8]
st.caption(f"DB: {DB_URL[:60]}…  (key {DBKEY})")

# --- controls to avoid stale IDs when switching DBs ---
colA, colB = st.columns([1, 1])
with colA:
    if st.button("🔄 Refresh pickers"):
        st.cache_data.clear()
        st.success("Pickers refreshed (cache cleared).")
with colB:
    if st.button("🧹 Reset selections"):
        for k in list(st.session_state.keys()):
            if k.endswith(f"_{DBKEY}") or k.startswith(f"fish_{DBKEY}") or k.startswith(f"treat_{DBKEY}"):
                del st.session_state[k]
        st.success("Selections cleared for this DB.")

# --- cached loaders (DB-aware) ---
@st.cache_data(ttl=60)
def _fish_options(q: Optional[str], dburl: str):
    with engine.begin() as conn:
        rows = Q.list_fish_minimal(conn, q=q, limit=200)
    return [(r["fish_code"], r["id_uuid"]) for r in rows]

@st.cache_data(ttl=60)
def _treatment_options(q: Optional[str], dburl: str):
    with engine.begin() as conn:
        rows = Q.list_treatments_minimal(conn, q=q, limit=200)  # returns treatment_type + id_uuid
    return [(r["treatment_type"], r["id_uuid"]) for r in rows]

# ===================== UI =====================
with st.container(border=True):
    st.subheader("1) Pick fish")
    qfish = st.text_input("Search fish_code", placeholder="type to filter…", key=f"fish_search_{DBKEY}")
    fish_choices = _fish_options(qfish, DB_URL)
    fish_label_to_id = {lbl: fid for lbl, fid in fish_choices}
    fish_labels = st.multiselect(
        "Fish",
        options=[lbl for lbl, _ in fish_choices],
        key=f"fish_{DBKEY}"
    )

with st.container(border=True):
    st.subheader("2) Pick treatment")
    qtreat = st.text_input("Search treatments", placeholder="treatment_type…", key=f"treat_search_{DBKEY}")
    treat_choices = _treatment_options(qtreat, DB_URL)
    treat_label_to_id = {lbl: tid for lbl, tid in treat_choices}
    treat_label = (
        st.selectbox("Treatment", options=[lbl for lbl, _ in treat_choices], key=f"treat_{DBKEY}")
        if treat_choices else None
    )

with st.container(border=True):
    st.subheader("3) When & metadata")
    d = st.date_input("applied_on", value=datetime.now().date(), key=f"date_{DBKEY}")
    t = st.time_input("time", value=datetime.now().time().replace(microsecond=0), key=f"time_{DBKEY}")
    applied_at = datetime.combine(d, t)

    col1, col2 = st.columns(2)
    with col1:
        batch_label = st.text_input("batch_label", placeholder="optional cohort/run", key=f"batch_{DBKEY}")
    with col2:
        created_by = st.text_input("created_by", placeholder="your initials", key=f"by_{DBKEY}")

    submit_ok = bool(fish_labels and treat_label and applied_at)

    if st.button("Apply treatment", type="primary", use_container_width=True, disabled=not submit_ok, key=f"apply_{DBKEY}"):
        try:
            count = 0
            with engine.begin() as conn:
                treatment_id = treat_label_to_id[treat_label]
                for lbl in fish_labels:
                    fid = fish_label_to_id[lbl]
                    Q.insert_fish_treatment_minimal(
                        conn,
                        fish_id=fid,
                        treatment_id=treatment_id,
                        applied_at=applied_at.isoformat(),
                        batch_label=(batch_label or None),
                        created_by=(created_by or None),
                    )
                    count += 1
            st.success(f"Inserted {count} treatment event(s).") if count else st.info("No rows inserted (duplicate key?).")
        except Exception as e:
            st.exception(e)

st.divider()
st.caption("Compatible mode: uses existing tables (fish, treatments, fish_treatments). Pickers are DB-aware to avoid stale UUIDs.")