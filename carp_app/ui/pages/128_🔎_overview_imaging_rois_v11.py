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

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock() -> None:
        ...

from carp_app.ui.lib.app_ctx import get_engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — v11 Imaging ROIs overview",
    page_icon="📷",
    layout="wide",
)
st.title("📷 v11 Imaging ROIs overview")

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
with st.form("roi_filters_v11", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 2, 0.8])
    with c1:
        q_raw = st.text_input(
            "Search (clutch / plate / slot / ROI code / anatomy / experiment)",
            "",
        )
    with c2:
        clutch_date_from_raw = st.text_input(
            "Clutch date from (YYYY-MM-DD, optional)",
            "",
        )
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
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)
clutch_date_from = _norm(clutch_date_from_raw)

# ───────── build WHERE for v11_imaging_roi_star ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  v.clutch_code     ILIKE :ql"
        " OR v.plate_code    ILIKE :ql"
        " OR v.slot_label    ILIKE :ql"
        " OR v.roi_code      ILIKE :ql"
        " OR v.roi_note_anatomy ILIKE :ql"
        " OR v.experiment_name ILIKE :ql"
        ")"
    )

if clutch_date_from:
    try:
        dt = datetime.strptime(clutch_date_from, "%Y-%m-%d").date()
        params["clutch_date_from"] = dt.isoformat()
        where.append("v.clutch_date >= :clutch_date_from")
    except ValueError:
        st.warning("Clutch date from must be in YYYY-MM-DD format.")
        st.stop()

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      v.roi_id,
      v.plate_code,
      v.slot_label,
      v.roi_index,
      v.roi_code,
      v.roi_note_anatomy,
      v.roi_path,
      v.experiment_date,
      v.experiment_name,
      v.clutch_code,
      v.clutch_date,
      v.estimated_egg_count,
      v.membership_role,
      v.embryo_count,
      v.fish_code,
      v.line_instance_code,
      v.line_code,
      v.group_code
    FROM public.v11_imaging_roi_star v
    WHERE {where_sql}
    ORDER BY v.plate_code, v.slot_label, v.roi_index
    LIMIT :lim;
""")

try:
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
except Exception as e:
    st.error("Error querying v11_imaging_roi_star.")
    st.exception(e)
    st.stop()

for c in df.select_dtypes(include=["object", "string"]).columns:
    df[c] = df[c].astype("string").fillna("")

st.caption(f"{len(df)} ROI row(s)")

# ───────── table ─────────
if df.empty:
    st.info("No imaging ROIs match the current filters.")
else:
    view = df.copy()
    view.insert(0, "✓ Select", False)

    st.data_editor(
        view,
        key="v11_imaging_rois_overview",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_order=[
            "✓ Select",
            "plate_code",
            "slot_label",
            "roi_index",
            "roi_code",
            "roi_note_anatomy",
            "roi_path",
            "experiment_date",
            "experiment_name",
            "clutch_code",
            "clutch_date",
            "estimated_egg_count",
            "membership_role",
            "embryo_count",
            "fish_code",
            "line_instance_code",
            "line_code",
            "group_code",
        ],
        column_config={
            "✓ Select":        st.column_config.CheckboxColumn("✓", default=False),
            "plate_code":      st.column_config.TextColumn("Plate", disabled=True),
            "slot_label":      st.column_config.TextColumn("Slot", disabled=True),
            "roi_index":       st.column_config.NumberColumn("ROI idx", disabled=True),
            "roi_code":        st.column_config.TextColumn("ROI code", disabled=True),
            "roi_note_anatomy": st.column_config.TextColumn("Anatomy", disabled=True),
            "roi_path":        st.column_config.TextColumn("ROI path", disabled=True),
            "experiment_date": st.column_config.DateColumn("Exp date", disabled=True),
            "experiment_name": st.column_config.TextColumn("Experiment", disabled=True),
            "clutch_code":     st.column_config.TextColumn("Clutch", disabled=True),
            "clutch_date":     st.column_config.DateColumn("Clutch date", disabled=True),
            "estimated_egg_count": st.column_config.NumberColumn("Est eggs", disabled=True),
            "membership_role": st.column_config.TextColumn("Role", disabled=True),
            "embryo_count":    st.column_config.NumberColumn("Embryos", disabled=True),
            "fish_code":       st.column_config.TextColumn("FSH code", disabled=True),
            "line_instance_code": st.column_config.TextColumn("LINE inst", disabled=True),
            "line_code":       st.column_config.TextColumn("LINE code", disabled=True),
            "group_code":      st.column_config.TextColumn("Group", disabled=True),
        },
    )

    st.download_button(
        "⬇︎ Download v11 imaging ROI star (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="v11_imaging_roi_star_overview.csv",
        type="secondary",
        mime="text/csv",
    )
