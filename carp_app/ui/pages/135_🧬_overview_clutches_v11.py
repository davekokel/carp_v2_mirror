# carp_app/ui/pages/135_🧬_overview_clutches_v11.py
from __future__ import annotations
import os, sys, pathlib
from datetime import date
from typing import Optional, Sequence

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine as _create_engine
from carp_app.lib.time import utc_now


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — v11 Clutch Overview",
    page_icon="🧬",
    layout="wide",
)
st.title("🧬 v11 Clutch Overview — Clutches (genotype + treatment)")


# ───────── engine helper ─────────
@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    return _create_engine()


# ───────── data loaders ─────────
@st.cache_data(show_spinner=True)
def load_clutches(
    _engine: Engine,
    date_min: Optional[date],
    date_max: Optional[date],
    text_filter: str,
    row_limit: int,
) -> pd.DataFrame:
    clauses = []
    params: dict[str, object] = {}

    if date_min is not None:
        clauses.append("c.clutch_date >= :date_min")
        params["date_min"] = date_min
    if date_max is not None:
        clauses.append("c.clutch_date <= :date_max")
        params["date_max"] = date_max

    sql = """
        SELECT
          clutch_code,
          clutch_date,
          n_imaging_slots,
          n_rois,
          treatments_and_transgenes,
          all_fluor_tag_rollup,
          all_organelle_fluor_rollup,
          treat_codes
        FROM public.v11_clutch_star c
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += """
        ORDER BY clutch_date, clutch_code
        LIMIT :row_limit
    """
    params["row_limit"] = row_limit

    with _engine.begin() as cx:
        df = pd.read_sql(text(sql), cx, params=params)

    # text filter over the main semantic fields
    text_filter = (text_filter or "").strip()
    if text_filter:
        f = text_filter.lower()

        def _match(row) -> bool:
            haystack = " ".join(
                str(row.get(col, "")) for col in [
                    "clutch_code",
                    "treatments_and_transgenes",
                    "all_fluor_tag_rollup",
                    "all_organelle_fluor_rollup",
                    "treat_codes",
                ]
            ).lower()
            return f in haystack

        mask = df.apply(_match, axis=1)
        df = df.loc[mask].reset_index(drop=True)

    return df


@st.cache_data(show_spinner=True)
def load_rois_for_clutches(
    _engine: Engine,
    clutch_codes: Sequence[str],
) -> pd.DataFrame:
    if not clutch_codes:
        return pd.DataFrame(
            columns=[
                "clutch_code",
                "plate_code",
                "slot_label",
                "roi_code",
                "roi_index",
                "roi_note_anatomy",
                "roi_path",
                "fish_code",
                "fish_genotype_pretty",
            ]
        )

    sql = text("""
        SELECT
          clutch_code,
          plate_code,
          slot_label,
          roi_code,
          roi_index,
          roi_note_anatomy,
          roi_path,
          fish_code,
          fish_genotype_pretty
        FROM public.v11_imaging_roi_star
        WHERE clutch_code = ANY(:codes)
        ORDER BY clutch_code, plate_code, slot_label, roi_index;
    """)

    with _engine.begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": list(clutch_codes)})

    return df


# ───────── controls ─────────
engine = get_engine()

col_filter, col_limit, col_meta = st.columns([4, 1, 2])

with col_filter:
    text_filter = st.text_input(
        "Search (clutch / genotype / treatment / markers)",
        value="",
        key="v11_clutches_text_filter",
        placeholder="e.g. mStayGold, PDQM-005, gu23, T-LEGACY-014…",
    )

with col_limit:
    row_limit = st.number_input(
        "Row limit",
        min_value=10,
        max_value=5000,
        value=1000,
        step=10,
        key="v11_clutches_row_limit",
    )

with col_meta:
    today = utc_now().date()
    default_start = date(today.year, 4, 1)
    st.write("Now:", utc_now().isoformat(timespec="seconds"))
    st.caption("Use dates below to narrow the legacy clutch window.")

col_dates1, col_dates2 = st.columns(2)
with col_dates1:
    date_min = st.date_input(
        "From date",
        value=default_start,
        key="v11_clutches_date_min",
    )
with col_dates2:
    date_max = st.date_input(
        "To date",
        value=today,
        key="v11_clutches_date_max",
    )

# ───────── main clutch table with selection ─────────
df_clutches = load_clutches(
    _engine=engine,
    date_min=date_min,
    date_max=date_max,
    text_filter=text_filter,
    row_limit=int(row_limit),
)

st.markdown(f"**{len(df_clutches)}** clutch row(s)")

if df_clutches.empty:
    st.info("No clutches matched the current filters.")
    selected_codes: list[str] = []
else:
    display_cols = [
        "clutch_code",
        "clutch_date",
        "n_imaging_slots",
        "n_rois",
        "treatments_and_transgenes",
        "all_fluor_tag_rollup",
        "all_organelle_fluor_rollup",
        "treat_codes",
    ]
    display_cols = [c for c in display_cols if c in df_clutches.columns]

    df_display = df_clutches[display_cols].copy()
    df_display.insert(0, "selected", False)

    edited = st.data_editor(
        df_display,
        height=450,
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        key="v11_clutches_editor",
    )

    selected_codes = edited.loc[edited["selected"], "clutch_code"].tolist()

# ───────── ROI drill-down for selected clutches ─────────
st.subheader("Imaging ROIs for selected clutch(es)", anchor=False)

if not selected_codes:
    st.caption("Select one or more clutches above to see their ROIs.")
else:
    df_rois = load_rois_for_clutches(engine, selected_codes)

    st.caption(f"{len(df_rois)} ROI row(s) for {len(selected_codes)} clutch(es).")

    if df_rois.empty:
        st.info("No ROIs found for the selected clutches in v11_imaging_roi_star.")
    else:
        roi_cols = [
            "clutch_code",
            "plate_code",
            "slot_label",
            "roi_code",
            "roi_index",
            "roi_note_anatomy",
            "roi_path",
            "fish_code",
            "fish_genotype_pretty",
        ]
        roi_cols = [c for c in roi_cols if c in df_rois.columns]
        st.dataframe(
            df_rois[roi_cols],
            height=400,
            use_container_width=True,
        )