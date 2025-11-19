# carp_app/ui/pages/126_📷_overview_imaging_rois.py
from __future__ import annotations

import sys, pathlib, os
from typing import Optional, List

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ---- path/auth bootstrap ----------------------------------------------------
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

# ---- auth & page config -----------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 📷 Overview imaging ROIs",
    page_icon="📷",
    layout="wide",
)
st.title("📷 Overview imaging ROIs")


@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return _engine()


def _normalize_q(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ---- filters ---------------------------------------------------------------
with st.form("roi_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        q_raw = st.text_input(
            "Search (plate / slot / fish / ROI / genotype / markers)",
            "",
            help=(
                "Matches plate_id_filled, slot_id_filled, fish_code, roi_name, "
                "genotype_pretty, all_marker_fluor_codes"
            ),
        )
    with c2:
        plate_filter = st.text_input("Plate ID contains", "")
    with c3:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=1000,
                step=50,
            )
        )
    submitted = st.form_submit_button("Apply")

q = _normalize_q(q_raw)
plate_filter = _normalize_q(plate_filter)

# ---- query ------------------------------------------------------------------
sql = text(
    """
    SELECT
      roi_code             AS imaging_roi_id,
      plate_id_filled      AS plate_code,
      slot_id_filled       AS slot_label,
      fish_code,
      roi_name,
      genotype_pretty,
      all_marker_fluor_codes,
      parent_female,
      parent_male,
      birthday,
      genetic_background,
      data_path
    FROM public.v_roi_overview
    WHERE
      (:plate_filter IS NULL OR COALESCE(plate_id_filled,'') ILIKE :plate_like)
      AND (
        :q IS NULL
        OR COALESCE(plate_id_filled,'')        ILIKE :ql
        OR COALESCE(slot_id_filled,'')         ILIKE :ql
        OR COALESCE(fish_code,'')              ILIKE :ql
        OR COALESCE(roi_name,'')               ILIKE :ql
        OR COALESCE(genotype_pretty,'')        ILIKE :ql
        OR COALESCE(all_marker_fluor_codes,'') ILIKE :ql
      )
    ORDER BY
      plate_id_filled NULLS LAST,
      slot_id_filled  NULLS LAST,
      imaging_roi_id  NULLS LAST
    LIMIT :lim
    """
)

params = {
    "q": q,
    "ql": f"%{q}%" if q else None,
    "plate_filter": plate_filter,
    "plate_like": f"%{plate_filter}%" if plate_filter else None,
    "lim": lim,
}

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} ROI row(s)")

# ---- table view -------------------------------------------------------------
if df.empty:
    st.info("No ROIs matched your filters.")
else:
    ro = df.copy()
    ro.insert(0, "✓ Select", False)

    ro_view = st.data_editor(
        ro,
        key="roi_overview_readonly",
        width="stretch",
        hide_index=True,
        height=600,
        column_config={
            "✓ Select":          st.column_config.CheckboxColumn("✓ Select"),
            "imaging_roi_id":    st.column_config.TextColumn("ROI code", disabled=True),
            "plate_code":        st.column_config.TextColumn("Plate", disabled=True),
            "slot_label":        st.column_config.TextColumn("Slot", disabled=True),
            "fish_code":         st.column_config.TextColumn("Fish code", disabled=True),
            "roi_name":          st.column_config.TextColumn("ROI name", disabled=True),
            "genotype_pretty":   st.column_config.TextColumn("Genotype (pretty)", disabled=True),
            "all_marker_fluor_codes": st.column_config.TextColumn("Markers (fluors)", disabled=True),
            "parent_female":     st.column_config.TextColumn("Female parent", disabled=True),
            "parent_male":       st.column_config.TextColumn("Male parent", disabled=True),
            "birthday":          st.column_config.TextColumn("Birthday", disabled=True),
            "genetic_background":st.column_config.TextColumn("Genetic background", disabled=True),
            "data_path":         st.column_config.TextColumn("Data path", disabled=True),
        },
    )

    st.divider()

    # selection summary + download
    selected_ids: List[str] = []
    if isinstance(ro_view, pd.DataFrame) and "✓ Select" in ro_view.columns:
        selected_ids = (
            ro_view.loc[ro_view["✓ Select"] == True, "imaging_roi_id"]
            .astype(str)
            .tolist()
        )

    st.subheader("Export")
    cL, cR = st.columns([3, 1])
    with cL:
        st.caption("Download the current view as CSV")
        st.download_button(
            "⬇︎ Download filtered ROIs (CSV)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"roi_overview_{len(df)}_rows.csv",
            type="secondary",
            mime="text/csv",
            use_container_width=True,
        )
    with cR:
        st.metric("Selected rows", len(selected_ids))