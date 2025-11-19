# carp_app/ui/pages/191_📷_overview_imaging_rois.py
from __future__ import annotations

import sys
import pathlib
from typing import Optional

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
    def require_app_unlock() -> None:
        ...
from carp_app.ui.lib.page_engine import engine as _engine

# ---- auth / page -------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="📷 Overview imaging clutches → ROIs",
    page_icon="📷",
    layout="wide",
)
st.title("📷 Overview imaging clutches → ROIs")


@st.cache_resource(show_spinner=False)
def eng() -> Engine:
    return _engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ---- filters -----------------------------------------------------------------
with st.form("filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([2, 2, 1])

    with c1:
        clutch_filter_raw = st.text_input(
            "Clutch code contains (IMG_CLT_…)",
            "",
        )
        treat_filter_raw = st.text_input(
            "Treatment code contains (IMG_TRT_…)",
            "",
        )
    with c2:
        free_q_raw = st.text_input(
            "Free text search (ROI name / path / markers / genotype)",
            "",
        )
    with c3:
        limit = int(
            st.number_input(
                "Row limit",
                min_value=50,
                max_value=5000,
                value=1000,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply", use_container_width=True)

clutch_filter = _norm(clutch_filter_raw)
treat_filter = _norm(treat_filter_raw)
free_q = _norm(free_q_raw)

# ---- SQL query ---------------------------------------------------------------
sql = text(
    """
    SELECT
      clutch_id,
      clutch_code,
      clutch_date,
      estimated_egg_count,
      clutch_notes,
      genotype_cross_label,
      genotype_base_codes,
      genotype_allele_codes,
      genotype_pretty,
      sheet_row_index,
      date_mount,
      mount_id,
      slot_index_global,
      plate_index,
      slot_index,
      experimental_plate_id,
      experimental_slot_id,
      data_location,
      treatment_id,
      treat_code,
      treat_text,
      kind_code,
      treatment_notes,
      treatment_plasmid_base_codes,
      treatment_rna_base_codes,
      treatment_dye_base_codes,
      treatment_marker_fluor_codes,
      treatment_marker_fluor_names,
      treatment_marker_tag_codes,
      treatment_marker_tag_names,
      all_base_codes,
      imaging_roi_id,
      slot_id,
      roi_index,
      roi_name,
      data_path,
      channel_info,
      roi_notes,
      roi_created_at
    FROM public.v_imaging_clutches_rois
    WHERE
      (:clutch_filter IS NULL OR clutch_code ILIKE :clutch_like)
      AND (:treat_filter IS NULL OR treat_code ILIKE :treat_like)
      AND (
        :free_q IS NULL
        OR COALESCE(roi_name,'')                   ILIKE :free_like
        OR COALESCE(data_path,'')                  ILIKE :free_like
        OR COALESCE(clutch_notes,'')               ILIKE :free_like
        OR COALESCE(treatment_notes,'')            ILIKE :free_like
        OR COALESCE(genotype_cross_label,'')       ILIKE :free_like
        OR COALESCE(genotype_base_codes,'')        ILIKE :free_like
        OR COALESCE(treatment_marker_fluor_codes,'') ILIKE :free_like
        OR COALESCE(treatment_marker_tag_codes,'') ILIKE :free_like
        OR COALESCE(all_base_codes,'')             ILIKE :free_like
      )
    ORDER BY clutch_date, clutch_code, experimental_slot_id, roi_index
    LIMIT :lim
    """
)

params = {
    "clutch_filter": clutch_filter,
    "clutch_like": f"%{clutch_filter}%" if clutch_filter else None,
    "treat_filter": treat_filter,
    "treat_like": f"%{treat_filter}%" if treat_filter else None,
    "free_q": free_q,
    "free_like": f"%{free_q}%" if free_q else None,
    "lim": limit,
}

with eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} row(s) from v_imaging_clutches_rois")

if df.empty:
    st.info("No imaging clutches / ROIs matched your filters.")
else:
    # Put the interesting columns up front
    preferred_cols = [
        "clutch_code",
        "clutch_date",
        "estimated_egg_count",
        "genotype_cross_label",
        "genotype_base_codes",
        "genotype_pretty",
        "treat_code",
        "treat_text",
        "treatment_marker_fluor_codes",
        "treatment_marker_tag_codes",
        "all_base_codes",
        "date_mount",
        "experimental_plate_id",
        "experimental_slot_id",
        "roi_index",
        "roi_name",
        "data_path",
    ]
    existing = [c for c in preferred_cols if c in df.columns]
    other_cols = [c for c in df.columns if c not in existing]

    display_df = df[existing + other_cols] if existing else df

    st.data_editor(
        display_df,
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key="imaging_clutches_rois_overview",
    )

    st.download_button(
        "⬇︎ Download CSV",
        data=display_df.to_csv(index=False).encode("utf-8"),
        file_name="imaging_clutches_rois.csv",
        mime="text/csv",
        use_container_width=True,
    )