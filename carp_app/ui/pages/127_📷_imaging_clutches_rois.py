from __future__ import annotations

import os
import pathlib
import sys
from datetime import datetime
from typing import Optional, Dict, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── repo bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.lib.app_ctx import get_engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock():
        ...

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Imaging clutches → ROIs",
    page_icon="📷",
    layout="wide",
)
st.title("📷 Imaging clutches → ROIs")

# ───────── engine (cached) ─────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return get_engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── filters ─────────
with st.form("imaging_clutches_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 2, 2, 0.8])
    with c1:
        q_raw = st.text_input(
            "Clutch code / parents / fish / ROI",
            "",
        )
    with c2:
        marker_raw = st.text_input(
            "Marker (fluor substring)",
            "",
        )
    with c3:
        clutch_date_from_raw = st.text_input(
            "Clutch date from (YYYY-MM-DD)",
            "",
        )
    with c4:
        lim = int(
            st.number_input(
                "Row limit",
                min_value=50,
                max_value=5000,
                value=1000,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)
marker = _norm(marker_raw)
clutch_date_from = _norm(clutch_date_from_raw)


# ───────── build WHERE for v_imaging_clutches_rois ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  COALESCE(clutch_code,'')      ILIKE :ql"
        " OR COALESCE(parent_female,'')  ILIKE :ql"
        " OR COALESCE(parent_male,'')    ILIKE :ql"
        " OR COALESCE(fish_code,'')      ILIKE :ql"
        " OR COALESCE(roi_code,'')       ILIKE :ql"
        " OR COALESCE(roi_name,'')       ILIKE :ql"
        ")"
    )

if marker:
    params["marker"] = f"%{marker}%"
    where.append("COALESCE(all_marker_fluor_codes,'') ILIKE :marker")

if clutch_date_from:
    try:
        # Validate date format and use as text comparable to date column
        dt = datetime.strptime(clutch_date_from, "%Y-%m-%d").date()
        params["clutch_date_from"] = dt.isoformat()
        where.append("clutch_date >= :clutch_date_from")
    except ValueError:
        st.warning("Clutch date from must be in YYYY-MM-DD format.")
        st.stop()

where_sql = " AND ".join(where)


# ───────── query canonical view v_imaging_clutches_rois ─────────
sql = text(f"""
    SELECT
      clutch_code,
      clutch_date,
      estimated_egg_count,
      membership_id,
      membership_role,
      embryo_count,
      mount_notes,
      membership_created_at,
      plate_code,
      slot_label,
      roi_code,
      roi_index,
      roi_name,
      fish_code,
      parent_female,
      parent_male,
      roi_birthday,
      all_marker_fluor_codes,
      data_path
    FROM public.v_imaging_clutches_rois
    WHERE {where_sql}
    ORDER BY clutch_code, plate_code, slot_label, roi_index
    LIMIT :lim
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

for c in df.select_dtypes(include=["object", "string"]).columns:
    df[c] = df[c].astype("string").fillna("")

st.caption(f"{len(df)} row(s)")


# ───────── main table ─────────
view = df.copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    key="imaging_clutches_rois_overview_v8",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "clutch_code",
        "clutch_date",
        "estimated_egg_count",
        "membership_role",
        "embryo_count",
        "plate_code",
        "slot_label",
        "roi_code",
        "roi_index",
        "roi_name",
        "fish_code",
        "parent_female",
        "parent_male",
        "roi_birthday",
        "all_marker_fluor_codes",
        "data_path",
    ],
    column_config={
        "✓ Select":          st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code":       st.column_config.TextColumn("Clutch code", disabled=True),
        "clutch_date":       st.column_config.DateColumn("Clutch date", disabled=True),
        "estimated_egg_count": st.column_config.NumberColumn("Est. egg count", disabled=True),
        "membership_role":   st.column_config.TextColumn("Role", disabled=True),
        "embryo_count":      st.column_config.NumberColumn("Embryos", disabled=True),
        "plate_code":        st.column_config.TextColumn("Plate", disabled=True),
        "slot_label":        st.column_config.TextColumn("Slot", disabled=True),
        "roi_code":          st.column_config.TextColumn("ROI code", disabled=True),
        "roi_index":         st.column_config.NumberColumn("ROI index", disabled=True),
        "roi_name":          st.column_config.TextColumn("ROI name", disabled=True),
        "fish_code":         st.column_config.TextColumn("Fish code", disabled=True),
        "parent_female":     st.column_config.TextColumn("Parent ♀", disabled=True),
        "parent_male":       st.column_config.TextColumn("Parent ♂", disabled=True),
        "roi_birthday":      st.column_config.DateColumn("ROI birthday", disabled=True),
        "all_marker_fluor_codes": st.column_config.TextColumn("Markers (fluors)", disabled=True),
        "data_path":         st.column_config.TextColumn("Data path", disabled=True),
    },
)

# ───────── export ─────────
st.download_button(
    "⬇︎ Download imaging clutches → ROIs (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="imaging_clutches_rois_overview.csv",
    type="secondary",
    mime="text/csv",
)
