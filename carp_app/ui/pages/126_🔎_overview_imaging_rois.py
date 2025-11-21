# carp_app/ui/pages/126_🔎_overview_imaging_rois.py
from __future__ import annotations

import os
import pathlib
import sys
from typing import Optional, Dict, Any, Any as AnyType

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
            "Search (plate / slot / fish / ROI / markers / fusions / locs)",
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

# ───────── query v_roi_overview + imaging_roi_annotations ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if plate_like:
    params["plate_like"] = f"%{plate_like}%"
    where.append("v.plate_code ILIKE :plate_like")

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  COALESCE(v.plate_code,'')                       ILIKE :ql"
        " OR COALESCE(v.slot_label,'')                     ILIKE :ql"
        " OR COALESCE(v.fish_code,'')                      ILIKE :ql"
        " OR COALESCE(v.roi_name,'')                       ILIKE :ql"
        " OR COALESCE(v.genotype_pretty,'')                ILIKE :ql"
        " OR COALESCE(v.genotype_base_codes,'')            ILIKE :ql"
        " OR COALESCE(v.genotype_marker_fluor_codes,'')    ILIKE :ql"
        " OR COALESCE(v.genotype_marker_tag_codes,'')      ILIKE :ql"
        " OR COALESCE(v.treatment_marker_fluor_codes,'')   ILIKE :ql"
        " OR COALESCE(v.treatment_marker_tag_codes,'')     ILIKE :ql"
        " OR COALESCE(v.all_marker_fluor_codes,'')         ILIKE :ql"
        " OR COALESCE(a.genotype_marker_fusion_labels,'')  ILIKE :ql"
        " OR COALESCE(a.treatment_marker_fusion_labels,'') ILIKE :ql"
        " OR COALESCE(a.genotype_marker_localizations,'')  ILIKE :ql"
        " OR COALESCE(a.treatment_marker_localizations,'') ILIKE :ql"
        " OR COALESCE(a.genotype_marker_fluor_loc_labels,'')  ILIKE :ql"
        " OR COALESCE(a.treatment_marker_fluor_loc_labels,'') ILIKE :ql"
        " OR COALESCE(v.data_path,'')                     ILIKE :ql"
        ")"
    )

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      v.imaging_roi_id,
      v.plate_code,
      v.slot_label,
      v.fish_code,
      v.roi_index,
      v.roi_name,
      v.parent_female,
      v.parent_male,
      v.birthday,
      v.genotype_pretty,
      v.genotype_base_codes,
      v.genotype_marker_fluor_codes,
      v.genotype_marker_tag_codes,
      v.treatment_marker_fluor_codes,
      v.treatment_marker_tag_codes,
      v.all_marker_fluor_codes,
      a.genotype_marker_fusion_labels,
      a.treatment_marker_fusion_labels,
      a.genotype_marker_localizations,
      a.treatment_marker_localizations,
      a.genotype_marker_fluor_loc_labels,
      a.treatment_marker_fluor_loc_labels,
      a.all_marker_fluor_loc_labels,
      v.data_path
    FROM public.v_roi_overview v
    LEFT JOIN public.imaging_roi_annotations a
      ON a.roi_dir = v.data_path
    WHERE {where_sql}
    ORDER BY
      v.plate_code NULLS LAST,
      v.slot_label NULLS LAST,
      v.roi_index NULLS LAST,
      v.imaging_roi_id NULLS LAST
    LIMIT :lim
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

# keep strings as strings; do not hide missing with fake defaults
for c in df.select_dtypes(include=["object", "string"]).columns:
    df[c] = df[c].astype("string")

st.caption(f"{len(df)} ROI(s)")

# ───────── derive all_marker_tag_codes, n_fluors, n_tags, booleans ─────────
def _merge_tags(row: pd.Series) -> Optional[str]:
    vals = []
    for col in ("genotype_marker_tag_codes", "treatment_marker_tag_codes"):
        v = row.get(col)
        if v is None or pd.isna(v):
            continue
        s = str(v).strip()
        if s:
            vals.append(s)
    if not vals:
        return None
    return ",".join(vals)

df["all_marker_tag_codes"] = df.apply(_merge_tags, axis=1)

def _count_items(val: AnyType) -> Optional[int]:
    if val is None or pd.isna(val):
        return None
    text = str(val).strip()
    if not text:
        return None
    items = [x.strip() for x in text.split(",") if x.strip()]
    return len(items) if items else None

df["n_fluors"] = df["all_marker_fluor_codes"].apply(_count_items)
df["n_tags"]   = df["all_marker_tag_codes"].apply(_count_items)

def _has_any(*vals: AnyType) -> bool:
    for v in vals:
        if v is None or pd.isna(v):
            continue
        if str(v).strip():
            return True
    return False

df["has_genotype_markers"] = df.apply(
    lambda r: _has_any(r.get("genotype_marker_fluor_codes"), r.get("genotype_marker_tag_codes")),
    axis=1,
)
df["has_treatment_markers"] = df.apply(
    lambda r: _has_any(r.get("treatment_marker_fluor_codes"), r.get("treatment_marker_tag_codes")),
    axis=1,
)
df["has_both_markers"] = df["has_genotype_markers"] & df["has_treatment_markers"]

# ───────── table ─────────
view = df.copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    key="roi_overview_v8",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "plate_code",
        "slot_label",
        "fish_code",
        "roi_index",
        "roi_name",
        "parent_female",
        "parent_male",
        "birthday",
        "genotype_pretty",
        "genotype_base_codes",
        "genotype_marker_fluor_codes",
        "genotype_marker_tag_codes",
        "genotype_marker_fusion_labels",
        "genotype_marker_localizations",
        "genotype_marker_fluor_loc_labels",
        "treatment_marker_fluor_codes",
        "treatment_marker_tag_codes",
        "treatment_marker_fusion_labels",
        "treatment_marker_localizations",
        "treatment_marker_fluor_loc_labels",
        "all_marker_fluor_codes",
        "all_marker_fluor_loc_labels",
        "all_marker_tag_codes",
        "n_fluors",
        "n_tags",
        "has_genotype_markers",
        "has_treatment_markers",
        "has_both_markers",
        "data_path",
    ],
    column_config={
        "✓ Select":          st.column_config.CheckboxColumn("✓", default=False),
        "plate_code":        st.column_config.TextColumn("Plate", disabled=True),
        "slot_label":        st.column_config.TextColumn("Slot", disabled=True),
        "fish_code":         st.column_config.TextColumn("Fish code", disabled=True),
        "roi_index":         st.column_config.NumberColumn("ROI idx", disabled=True),
        "roi_name":          st.column_config.TextColumn("ROI name", disabled=True),
        "parent_female":     st.column_config.TextColumn("Parent ♀", disabled=True),
        "parent_male":       st.column_config.TextColumn("Parent ♂", disabled=True),
        "birthday":          st.column_config.DateColumn("Birthday", disabled=True),
        "genotype_pretty":   st.column_config.TextColumn("Genotype (pretty)", disabled=True),
        "genotype_base_codes": st.column_config.TextColumn("Genotype base codes", disabled=True),
        "genotype_marker_fluor_codes": st.column_config.TextColumn("Genotype fluors", disabled=True),
        "genotype_marker_tag_codes":   st.column_config.TextColumn("Genotype tags", disabled=True),
        "genotype_marker_fusion_labels": st.column_config.TextColumn("Genotype fusions", disabled=True),
        "genotype_marker_localizations": st.column_config.TextColumn("Genotype locs", disabled=True),
        "genotype_marker_fluor_loc_labels": st.column_config.TextColumn("Genotype fluor(loc)", disabled=True),
        "treatment_marker_fluor_codes": st.column_config.TextColumn("Treatment fluors", disabled=True),
        "treatment_marker_tag_codes":   st.column_config.TextColumn("Treatment tags", disabled=True),
        "treatment_marker_fusion_labels": st.column_config.TextColumn("Treatment fusions", disabled=True),
        "treatment_marker_localizations": st.column_config.TextColumn("Treatment locs", disabled=True),
        "treatment_marker_fluor_loc_labels": st.column_config.TextColumn("Treatment fluor(loc)", disabled=True),
        "all_marker_fluor_codes":       st.column_config.TextColumn("All fluors", disabled=True),
        "all_marker_fluor_loc_labels":  st.column_config.TextColumn("All fluor(loc)", disabled=True),
        "all_marker_tag_codes":         st.column_config.TextColumn("All tags", disabled=True),
        "n_fluors":            st.column_config.NumberColumn("n_fluors", disabled=True),
        "n_tags":              st.column_config.NumberColumn("n_tags", disabled=True),
        "has_genotype_markers": st.column_config.CheckboxColumn("Genotype markers?", disabled=True),
        "has_treatment_markers": st.column_config.CheckboxColumn("Treatment markers?", disabled=True),
        "has_both_markers":     st.column_config.CheckboxColumn("Genotype + treatment?", disabled=True),
        "data_path":           st.column_config.TextColumn("Data path", disabled=True),
    },
)

# ───────── export ─────────
st.download_button(
    "⬇︎ Download ROI overview (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="imaging_rois_overview_v5.csv",
    type="secondary",
    mime="text/csv",
)