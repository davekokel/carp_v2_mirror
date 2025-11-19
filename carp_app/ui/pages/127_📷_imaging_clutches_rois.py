# carp_app/ui/pages/127_📷_imaging_clutches_rois.py
from __future__ import annotations

import os
import sys
import pathlib
from typing import Optional, List, Dict, Any

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
    def require_app_unlock() -> None:
        ...

from carp_app.ui.lib.page_engine import engine as _engine

# ---- auth / page ------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 📷 Imaging clutches → ROIs",
    page_icon="📷",
    layout="wide",
)
st.title("📷 Imaging clutches → ROIs")

# ---- engine helper ----------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL is not set; cannot connect to database.")
        st.stop()
    return _engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _view_exists(cx, schema: str, view: str) -> bool:
    sql = text(
        """
        SELECT EXISTS (
          SELECT 1
          FROM pg_views
          WHERE schemaname = :schema
            AND viewname   = :view
        )
        """
    )
    return bool(cx.execute(sql, {"schema": schema, "view": view}).scalar())


# ---- filters ----------------------------------------------------------------
with st.form("clutch_roi_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])

    with c1:
        clutch_q_raw = st.text_input(
            "Clutch code / parents / fish / ROI",
            "",
            help="Matches clutch_code, parent text, fish_code, roi_name.",
        )
    with c2:
        marker_q_raw = st.text_input(
            "Marker (fluor substring)",
            "",
            help="Matches all_marker_fluor_codes (e.g. 'mStayGold', 'Halo', 'tdmSG').",
        )
    with c3:
        date_from = st.date_input(
            "Clutch date from",
            value=None,
        )
    with c4:
        lim = int(
            st.number_input(
                "Row limit",
                min_value=100,
                max_value=5000,
                value=1000,
                step=100,
            )
        )

    submitted = st.form_submit_button("Apply", use_container_width=True)

clutch_q = _norm(clutch_q_raw)
marker_q = _norm(marker_q_raw)

params: Dict[str, Any] = {"lim": lim}
where_clauses = ["1=1"]

if clutch_q:
    params["clutch_q"] = f"%{clutch_q}%"
    where_clauses.append(
        """
        (
          COALESCE(r.clutch_code, '')             ILIKE :clutch_q
          OR COALESCE(r.zf_female_genotype_text,'') ILIKE :clutch_q
          OR COALESCE(r.zf_male_genotype_text,'')   ILIKE :clutch_q
          OR COALESCE(r.fish_code,'')               ILIKE :clutch_q
          OR COALESCE(r.roi_name,'')                ILIKE :clutch_q
        )
        """
    )

if marker_q:
    params["marker_q"] = f"%{marker_q}%"
    where_clauses.append(
        """
        COALESCE(r.all_marker_fluor_codes,'') ILIKE :marker_q
        """
    )

if date_from is not None:
    params["date_from"] = date_from
    where_clauses.append("r.clutch_date >= :date_from")

where_sql = " AND ".join(where_clauses)

eng = get_engine()
with eng.begin() as cx:
    if not _view_exists(cx, "public", "v_imaging_clutches_rois"):
        st.warning(
            "The view `public.v_imaging_clutches_rois` does not exist yet.\n\n"
            "This page will be enabled once the imaging clutches→ROIs view is "
            "defined in the database (via a migration)."
        )
        st.stop()

    sql = text(
        f"""
        SELECT
          r.clutch_code,
          r.clutch_date,
          r.estimated_egg_count,
          r.membership_date_born,
          r.zf_female_genotype_text,
          r.zf_male_genotype_text,
          r.data_location,

          r.imaging_roi_id,
          r.plate_code,
          r.slot_label,
          r.fish_code,
          r.roi_name,
          r.roi_parent_female,
          r.roi_parent_male,
          r.roi_birthday,
          r.all_marker_fluor_codes,
          r.data_path

        FROM public.v_imaging_clutches_rois AS r
        WHERE {where_sql}
        ORDER BY
          r.clutch_code,
          r.clutch_date,
          r.plate_code,
          r.slot_label,
          r.imaging_roi_id
        LIMIT :lim
        """
    )

    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} clutch→ROI row(s) from v_imaging_clutches_rois (limit {lim})")

if df.empty:
    st.info("No clutch/ROI chains matched the current filters.")
    st.stop()

# ---- add selection column ---------------------------------------------------
ro = df.copy()
ro.insert(0, "✓ Select", False)

column_config = {
    "clutch_code":        st.column_config.TextColumn("Clutch", disabled=True),
    "clutch_date":        st.column_config.DateColumn("Clutch date", disabled=True),
    "estimated_egg_count": st.column_config.NumberColumn("ROI count (inferred)", disabled=True),
    "membership_date_born": st.column_config.DateColumn("Membership date_born", disabled=True),
    "zf_female_genotype_text": st.column_config.TextColumn("Female genotype (legacy)", disabled=True),
    "zf_male_genotype_text":   st.column_config.TextColumn("Male genotype (legacy)", disabled=True),
    "data_location":      st.column_config.TextColumn("Data location (sheet / ROI dir)", disabled=True),

    "imaging_roi_id":     st.column_config.TextColumn("ROI ID", disabled=True),
    "plate_code":         st.column_config.TextColumn("Plate", disabled=True),
    "slot_label":         st.column_config.TextColumn("Slot", disabled=True),
    "fish_code":          st.column_config.TextColumn("Fish code", disabled=True),
    "roi_name":           st.column_config.TextColumn("ROI name", disabled=True),
    "roi_parent_female":  st.column_config.TextColumn("ROI parent female", disabled=True),
    "roi_parent_male":    st.column_config.TextColumn("ROI parent male", disabled=True),
    "roi_birthday":       st.column_config.DateColumn("ROI birthday", disabled=True),
    "all_marker_fluor_codes": st.column_config.TextColumn("Markers (fluors)", disabled=True),
    "data_path":          st.column_config.TextColumn("Data path", disabled=True),
}

ro_view = st.data_editor(
    ro,
    key="imaging_clutches_rois_readonly",
    width="stretch",
    hide_index=True,
    height=700,
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓ Select"),
        **column_config,
    },
)

st.divider()

# ---- selection + export -----------------------------------------------------
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
        "⬇︎ Download filtered clutch→ROI rows (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"imaging_clutches_rois_{len(df)}_rows.csv",
        type="secondary",
        mime="text/csv",
        use_container_width=True,
    )

with cR:
    st.metric("Selected ROIs", len(selected_ids))