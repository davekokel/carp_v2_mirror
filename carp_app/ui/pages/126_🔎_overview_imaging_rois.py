# carp_app/ui/pages/126_🔎_overview_imaging_rois.py
from __future__ import annotations

import os
import pathlib
import sys
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
    def require_app_unlock() -> None:
        ...


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview imaging ROIs",
    page_icon="📷",
    layout="wide",
)
st.title("📷 Overview imaging ROIs")


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
with st.form("roi_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 2, 0.8])
    with c1:
        q_raw = st.text_input(
            "Search (plate / slot / ROI code / anatomy / path)",
            "",
        )
    with c2:
        plate_like_raw = st.text_input(
            "Plate ID contains (optional)",
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
plate_like = _norm(plate_like_raw)

# ───────── query v_roi_overview (lean) ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if plate_like:
    params["plate_like"] = f"%{plate_like}%"
    where.append("v.plate_code ILIKE :plate_like")

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  v.plate_code       ILIKE :ql"
        " OR v.slot_label     ILIKE :ql"
        " OR v.roi_code       ILIKE :ql"
        " OR v.roi_note_anatomy ILIKE :ql"
        " OR v.roi_path       ILIKE :ql"
        " OR v.experiment_name ILIKE :ql"
        " OR v.scope_name     ILIKE :ql"
        " OR v.scope_settings ILIKE :ql"
        " OR v.plate_note     ILIKE :ql"
        " OR v.slot_note      ILIKE :ql"
        ")"
    )

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      v.roi_id,
      v.plate_code,
      v.experiment_date,
      v.experiment_name,
      v.scope_name,
      v.scope_settings,
      v.plate_note,
      v.slot_label,
      v.slot_index,
      v.slot_note,
      v.roi_index_within_slot AS roi_index,
      v.roi_code,
      v.roi_note_anatomy,
      v.roi_path,
      v.created_at
    FROM public.v_roi_overview v
    WHERE {where_sql}
    ORDER BY
      v.plate_code NULLS LAST,
      v.slot_label NULLS LAST,
      v.roi_index_within_slot NULLS LAST,
      v.roi_id NULLS LAST
    LIMIT :lim
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

# keep strings as strings; let NULLs be NULL (we'll fill "" only for display)
for c in df.select_dtypes(include=["object", "string"]).columns:
    df[c] = df[c].astype("string")

st.caption(f"{len(df)} ROI(s)")

# ───────── table ─────────
view = df.copy()
view.insert(0, "✓ Select", False)

st.data_editor(
    view,
    key="roi_overview_v9",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "plate_code",
        "experiment_date",
        "experiment_name",
        "scope_name",
        "scope_settings",
        "plate_note",
        "slot_label",
        "slot_index",
        "slot_note",
        "roi_index",
        "roi_code",
        "roi_note_anatomy",
        "roi_path",
        "created_at",
    ],
    column_config={
        "✓ Select":        st.column_config.CheckboxColumn("✓", default=False),
        "plate_code":      st.column_config.TextColumn("Plate", disabled=True),
        "experiment_date": st.column_config.DateColumn("Exp date", disabled=True),
        "experiment_name": st.column_config.TextColumn("Experiment", disabled=True),
        "scope_name":      st.column_config.TextColumn("Scope", disabled=True),
        "scope_settings":  st.column_config.TextColumn("Scope settings", disabled=True),
        "plate_note":      st.column_config.TextColumn("Plate note", disabled=True),
        "slot_label":      st.column_config.TextColumn("Slot", disabled=True),
        "slot_index":      st.column_config.NumberColumn("Slot idx", disabled=True),
        "slot_note":       st.column_config.TextColumn("Slot note", disabled=True),
        "roi_index":       st.column_config.NumberColumn("ROI idx", disabled=True),
        "roi_code":        st.column_config.TextColumn("ROI code", disabled=True),
        "roi_note_anatomy": st.column_config.TextColumn("ROI anatomy", disabled=True),
        "roi_path":        st.column_config.TextColumn("ROI path", disabled=True),
        "created_at":      st.column_config.DatetimeColumn("Created", disabled=True),
    },
)

# ───────── export ─────────
st.download_button(
    "⬇︎ Download ROI overview (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="imaging_rois_overview_v9.csv",
    type="secondary",
    mime="text/csv",
)