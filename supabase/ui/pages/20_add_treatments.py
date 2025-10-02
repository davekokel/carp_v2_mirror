# supabase/ui/pages/20_add_treatments.py
from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os
from datetime import datetime
from typing import Optional

import streamlit as st
from sqlalchemy import create_engine

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib
import supabase.queries as _queries
importlib.reload(_queries)
from supabase import queries as Q

PAGE_TITLE = "CARP — Add Treatments"
st.set_page_config(page_title=PAGE_TITLE, page_icon="💊")
st.title("💊 Add Treatments to Existing Fish")

DB_URL = os.environ.get("DB_URL")
if not DB_URL:
    st.stop()

engine = create_engine(DB_URL)

@st.cache_data(ttl=60)
def _treatment_options(q: Optional[str]):
    with engine.begin() as conn:
        rows = Q.list_treatments_minimal(conn, q=q, limit=200)
    return [(r["treatment_type"], r["id_uuid"]) for r in rows]

with st.container(border=True):
    st.subheader("1) Pick fish")
    qfish = st.text_input("Search fish_code", placeholder="type to filter…")
    fish_choices = _fish_options(qfish)
    fish_label_to_id = {lbl: fid for lbl, fid in fish_choices}
    fish_labels = st.multiselect("Fish", options=[lbl for lbl, _ in fish_choices])

with st.container(border=True):
    st.subheader("2) Pick treatment")
    qtreat = st.text_input("Search treatments", placeholder="treatment_type…")
    treat_choices = _treatment_options(qtreat)
    treat_label_to_id = {lbl: tid for lbl, tid in treat_choices}
    treat_label = st.selectbox("Treatment", options=[lbl for lbl, _ in treat_choices]) if treat_choices else None

with st.container(border=True):
    st.subheader("3) When & metadata")
    d = st.date_input("applied_on", value=datetime.now().date())
    t = st.time_input("time", value=datetime.now().time().replace(microsecond=0))
    applied_at = datetime.combine(d, t)

    col1, col2 = st.columns(2)
    with col1:
        batch_label = st.text_input("batch_label", placeholder="optional cohort/run")
    with col2:
        created_by = st.text_input("created_by", placeholder="your initials")

    submit_ok = bool(fish_labels and treat_label and applied_at)
    if st.button("Apply treatment", type="primary", use_container_width=True, disabled=not submit_ok):
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
            st.success(f"Inserted {count} treatment event(s).")
        except Exception as e:
            st.exception(e)

st.divider()
st.caption("Compatible mode: using existing columns. We can add dose/route later.")