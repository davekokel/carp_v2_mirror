# 03_🏷️_request_tank_labels.py
from __future__ import annotations

import os
from io import BytesIO
from typing import List, Dict, Any, Optional
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# ---------- Auth gate ----------
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

PAGE_TITLE = "CARP — Overview → PDF Labels"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🏷️")
st.title(PAGE_TITLE)

# ---------- Import helper from lib (robust fallbacks) ----------
# Expect one of these modules to exist in your repo.
_render_func = None
_render_err: Optional[str] = None
try:
    # Preferred name we used most recently
    from supabase.ui.lib.tank_label_maker import render_tank_labels_pdf as _render_func
except Exception as e1:  # noqa: F841
    try:
        from supabase.ui.lib.labels import render_tank_labels_pdf as _render_func
    except Exception as e2:  # noqa: F841
        try:
            from lib.tank_label_maker import render_tank_labels_pdf as _render_func
        except Exception as e3:  # noqa: F841
            try:
                from lib.labels import render_tank_labels_pdf as _render_func
            except Exception as e4:
                _render_err = (
                    "Could not import label helper. Expected one of: "
                    "supabase.ui.lib.tank_label_maker.render_tank_labels_pdf, "
                    "supabase.ui.lib.labels.render_tank_labels_pdf, lib.tank_label_maker.render_tank_labels_pdf, "
                    "or lib.labels.render_tank_labels_pdf"
                )

# ---------- DB engine ----------
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
# We load via the shared queries module; the page hot-reloads and should pick up edits.
import importlib
try:
    import supabase.queries as _queries
    importlib.reload(_queries)
    from supabase.queries import load_fish_overview
except Exception:
    # Local fallback for development runners that mount the repo differently
    import queries as _queries  # type: ignore
    importlib.reload(_queries)
    from queries import load_fish_overview  # type: ignore

# ---------- UI controls ----------
with st.sidebar:
    st.subheader("Filters")
    seed_filter = st.text_input("Seed batch ID contains", value="")
    text_filter = st.text_input("Name / Code contains", value="")
    show_only_unlabeled = st.checkbox("Show only fish without labels", value=False)
    st.caption("Use filters, then pick rows below to render labels.")

# ---------- Load data ----------
@st.cache_data(show_spinner=False)
def _load_overview_df() -> pd.DataFrame:
    # Expect load_fish_overview() to return at least these columns; extras are fine:
    # fish_code, id_uuid, name, nickname, line_building_stage, date_birth, genetic_background,
    # created_by_enriched, last_plasmid_injection_at, plasmid_injections_text,
    # last_rna_injection_at, rna_injections_text, batch_label
    return load_fish_overview(_get_engine())

df = _load_overview_df().copy()

# Defensive normalize of expected columns
for col in [
    "fish_code","id_uuid","name","nickname","line_building_stage","date_birth",
    "genetic_background","created_by_enriched","last_plasmid_injection_at",
    "plasmid_injections_text","last_rna_injection_at","rna_injections_text","batch_label"
]:
    if col not in df.columns:
        df[col] = None

# Apply filters
if seed_filter:
    df = df[df.get("batch_label", "").fillna("").str.contains(seed_filter, case=False, na=False) |
            df.get("seed_batch_id", pd.Series([""]*len(df))).astype(str).str.contains(seed_filter, case=False, na=False)]
if text_filter:
    m = (
        df.get("fish_code", "").astype(str).str.contains(text_filter, case=False, na=False) |
        df.get("name", "").astype(str).str.contains(text_filter, case=False, na=False) |
        df.get("nickname", "").astype(str).str.contains(text_filter, case=False, na=False)
    )
    df = df[m]

# Optional: only unlabeled — relies on a boolean or null check; if your schema differs, adjust below
if show_only_unlabeled and "has_label" in df.columns:
    df = df[df["has_label"].fillna(False) == False]  # noqa: E712

# Display table with a selection widget
st.subheader("Fish overview (select rows to print)")
# Keep the UX simple: a multiselect of fish_code, plus a convenience select-all toggle
all_codes = df["fish_code"].tolist()
col1, col2 = st.columns([3,1])
with col1:
    sel_codes = st.multiselect("Pick fish_code", options=all_codes, default=all_codes[:0])
with col2:
    if st.button("Select all visible"):
        sel_codes = all_codes

sel_df = df[df["fish_code"].isin(sel_codes)].copy() if sel_codes else df.head(0).copy()

# Show a compact view
if not sel_df.empty:
    show_cols = [
        "fish_code","name","nickname","line_building_stage","date_birth","genetic_background",
        "batch_label","created_by_enriched"
    ]
    show_cols = [c for c in show_cols if c in sel_df.columns]
    st.dataframe(sel_df[show_cols], hide_index=True, width=1200)
else:
    st.info("No rows selected.")

st.divider()

# ---------- Render labels ----------
if _render_func is None and _render_err:
    st.error(_render_err)
else:
    st.subheader("Render tank labels → PDF")
    cols = st.columns(4)
    with cols[0]:
        n_cols = st.number_input("Labels per row", min_value=1, max_value=5, value=3, step=1)
    with cols[1]:
        margin_mm = st.number_input("Page margin (mm)", min_value=0, max_value=25, value=6, step=1)
    with cols[2]:
        cutmarks = st.checkbox("Cut marks", value=True)
    with cols[3]:
        title = st.text_input("Header (optional)", value="")

    # Format rows for the helper: keep it simple — pass the DataFrame; helper can pick needed columns
    make_btn = st.button("Generate PDF", type="primary")
    if make_btn:
        if sel_df.empty:
            st.warning("Select at least one fish to render labels.")
        else:
            try:
                pdf_bytes: bytes = _render_func(
                    sel_df,
                    labels_per_row=int(n_cols),
                    page_margin_mm=int(margin_mm),
                    draw_cut_marks=bool(cutmarks),
                    header_text=title or None,
                )
                bio = BytesIO(pdf_bytes)
                st.download_button(
                    "Download labels PDF",
                    data=bio,
                    file_name="tank_labels.pdf",
                    mime="application/pdf",
                )
                st.success("PDF generated.")
            except Exception as e:
                st.error(f"Label rendering failed: {e}")

# ---------- Utility: quick counts from DB (optional, collapsible) ----------
with st.expander("Debug: recent batches & label link counts"):
    try:
        q = text(
            """
            with recent as (
              select seed_batch_id, max(logged_at) as last_seen
              from public.fish_seed_batches_map
              group by 1
              order by last_seen desc
              limit 20
            )
            select r.seed_batch_id, r.last_seen,
                   count(distinct f.id_uuid) as fish_count
            from recent r
            join public.fish_seed_batches_map m on m.seed_batch_id=r.seed_batch_id
            join public.fish f on f.id_uuid=m.fish_id
            group by 1,2
            order by r.last_seen desc
            """
        )
        with _get_engine().begin() as cx:
            dbg = pd.read_sql(q, cx)
        st.dataframe(dbg, hide_index=True)
    except Exception as e:
        st.caption(f"debug failed: {e}")
