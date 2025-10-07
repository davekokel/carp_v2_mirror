# 04_🏷️_assign_tank_labels_and_status.py
from __future__ import annotations

import os
from io import BytesIO
from typing import Optional, Dict, Any, List

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# ---------- Auth gate ----------
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:  # local dev
    from auth_gate import require_app_unlock
require_app_unlock()

PAGE_TITLE = "CARP — Assign Tank Labels (2.4×1.5 in)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🏷️")
st.title(PAGE_TITLE)

# ---- Quick reset (clears cache + selection grid) ----
if st.button("↻ Refresh data", key="btn_refresh_labels"):
    st.cache_data.clear()
    for k in list(st.session_state.keys()):
        if k.startswith(("assign_labels_table", "assign_editor", "_labels_df_sig", "_label_rows")):
            del st.session_state[k]
    st.rerun()

# ---------- DB ----------
ENGINE: Optional[Engine] = None
def _get_engine() -> Engine:
    global ENGINE
    if ENGINE:
        return ENGINE
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    ENGINE = create_engine(url, future=True, pool_pre_ping=True)
    return ENGINE

# ---------- Queries helper ----------
import importlib
try:
    import supabase.queries as _queries
    importlib.reload(_queries)
    from supabase.queries import load_label_rows
except Exception:
    import queries as _queries  # type: ignore
    importlib.reload(_queries)
    from queries import load_label_rows  # type: ignore

# ---------- Label builder ----------
try:
    from supabase.ui.lib.labels_roll_2x1_5 import build_pdf as _build_pdf
except Exception:
    from lib.labels_roll_2x1_5 import build_pdf as _build_pdf  # local fallback

# ---------- Load data ----------
@st.cache_data(show_spinner=False)
def _load_df(q: str, limit: int) -> pd.DataFrame:
    return load_label_rows(_get_engine(), q=q or None, limit=limit)

with st.sidebar:
    st.subheader("Filters")
    q = st.text_input("Search (code / name / nickname / genotype / background)", key="assign_q")
    lim = st.number_input("Limit", min_value=50, max_value=5000, value=500, step=50)
    apply = st.button("Apply", key="btn_apply")

if apply or "_label_rows" not in st.session_state:
    st.session_state["_label_rows"] = _load_df(q or "", int(lim))

df = st.session_state["_label_rows"].copy()

# Guarantee expected cols (vw_label_rows should already have these)
expected = [
    "fish_code","name","genotype_print",
    "nickname_print","genetic_background_print","line_building_stage_print","date_birth_print",
    "batch_label","transgene_base_code_filled","allele_code_filled","allele_name_filled",
    "id_uuid","created_at",
]
for c in expected:
    if c not in df.columns:
        df[c] = ""

# For display only, mirror overview naming
df["nickname"]            = df["nickname_print"]
df["genetic_background"]  = df["genetic_background_print"]
df["line_building_stage"] = df["line_building_stage_print"]
df["date_birth"]          = df["date_birth_print"]
df["genotype_display"]    = df["genotype_print"]

# ---------- Infinite-scroll table with checkboxes ----------
st.subheader("Fish overview (select rows to print)")

# Build the grid from FULL df (keep hidden fields for preview/PDF)
grid_df = df.copy()

KEY_TABLE = "assign_labels_table"
SIG_KEY   = "_labels_df_sig"
current_sig = (len(grid_df), tuple(grid_df.columns))

if (KEY_TABLE not in st.session_state) or (st.session_state.get(SIG_KEY) != current_sig):
    tbl = grid_df.copy()
    tbl.insert(0, "✓", False)
    st.session_state[KEY_TABLE] = tbl
    st.session_state[SIG_KEY]   = current_sig
else:
    prev = st.session_state[KEY_TABLE].set_index("fish_code")
    new  = grid_df.copy().set_index("fish_code")
    new.insert(0, "✓", False)
    ix = new.index.intersection(prev.index)
    if len(ix):
        new.loc[ix, "✓"] = prev.loc[ix, "✓"].values
    st.session_state[KEY_TABLE] = new.reset_index()

# Select/Clear buttons
c1, c2, _ = st.columns([1,1,6])
with c1:
    if st.button("Select all visible", key="btn_select_all"):
        ss = st.session_state[KEY_TABLE].copy()
        ss["✓"] = True
        st.session_state[KEY_TABLE] = ss
with c2:
    if st.button("Clear selection", key="btn_clear_sel"):
        ss = st.session_state[KEY_TABLE].copy()
        ss["✓"] = False
        st.session_state[KEY_TABLE] = ss

# Only DISPLAY these columns; hidden ones remain in the dataframe
display_cols = [
    "✓", "fish_code", "name", "nickname", "line_building_stage",
    "date_birth", "genetic_background", "genotype_display", "batch_label",
]

edited = st.data_editor(
    st.session_state[KEY_TABLE],
    column_order=[c for c in display_cols if c in st.session_state[KEY_TABLE].columns],
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    key="assign_editor",
)
st.session_state[KEY_TABLE] = edited

# Selected rows keep ALL hidden columns
selected = edited[edited["✓"]].copy()

st.divider()

# ---------- Preview selected (exactly what prints) ----------
st.subheader("Preview selected fields (exactly what prints)")
if st.button("Build preview table", key="btn_preview_assign"):
    if selected.empty:
        st.info("No rows selected.")
    else:
        preview_cols = [
            "fish_code","name","genotype_print",
            "nickname_print","genetic_background_print","line_building_stage_print","date_birth_print",
        ]
        for c in preview_cols:
            if c not in selected.columns:
                selected[c] = ""
        st.dataframe(selected[preview_cols], use_container_width=True, hide_index=True)

st.divider()

# ---------- Generate PDF ----------
st.subheader("Generate label PDF")
if st.button("Create PDF", type="primary", key="btn_pdf_assign"):
    if selected.empty:
        st.warning("Select at least one fish above.")
    else:
        rows: List[Dict[str, Any]] = []
        for _, r in selected.iterrows():
            rows.append({
                "fish_code": r.get("fish_code"),
                "name": r.get("name"),
                "genotype": r.get("genotype_print"),
                "nickname": r.get("nickname_print"),
                "tg_nick": r.get("genetic_background_print"),
                "stage": r.get("line_building_stage_print"),
                "dob": r.get("date_birth_print"),
                "base_code": r.get("transgene_base_code_filled"),  # optional
            })
        try:
            bio = BytesIO()
            _build_pdf(rows, bio)
            bio.seek(0)
            st.download_button(
                label="Download labels (2.4×1.5 in)",
                data=bio,
                file_name="tank_labels_2.4x1.5.pdf",
                mime="application/pdf",
                key="dl_pdf_assign",
            )
            st.success("PDF ready.")
        except Exception as e:
            st.error(f"Label rendering failed: {e}")