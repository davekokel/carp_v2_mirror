# carp_app/ui/pages/127_📷_imaging_clutches_rois.py
from __future__ import annotations

import os
import sys
import pathlib
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

# ---- filters -----------------------------------------------------------------
with st.form("clutch_roi_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])

    with c1:
        clutch_q_raw = st.text_input(
            "Clutch code / parents / treatment",
            "",
            help="Matches clutch_code, zf female/male genotype text, treatment codes/text.",
        )
    with c2:
        marker_q_raw = st.text_input(
            "Marker (fluor/tag substring)",
            "",
            help="Matches treatment marker fluor/tag codes (e.g. 'Halo', 'mSG', 'mScarlet3S2').",
        )
    with c3:
        date_from = st.date_input("Clutch date from", value=None)
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

params: dict[str, object] = {"lim": lim}
where_clauses = ["1=1"]

if clutch_q:
    params["clutch_q"] = f"%{clutch_q}%"
    where_clauses.append("""
        (
          c.clutch_code ILIKE :clutch_q
          OR COALESCE(zf_female_genotype_text, '') ILIKE :clutch_q
          OR COALESCE(zf_male_genotype_text, '') ILIKE :clutch_q
          OR COALESCE(treat_code, '') ILIKE :clutch_q
          OR COALESCE(treat_text, '') ILIKE :clutch_q
        )
    """)

if marker_q:
    params["marker_q"] = f"%{marker_q}%"
    where_clauses.append("""
        (
          COALESCE(treatment_marker_fluor_codes, '') ILIKE :marker_q
          OR COALESCE(treatment_marker_tag_codes, '') ILIKE :marker_q
        )
    """)

if date_from is not None:
    params["date_from"] = date_from
    where_clauses.append("c.clutch_date >= :date_from")

where_sql = " AND ".join(where_clauses)

# ---- query v_imaging_clutches_rois ------------------------------------------
sql = text(f"""
SELECT
  c.clutch_code,
  c.clutch_date,
  c.date_born,
  c.zf_female_genotype_text,
  c.zf_male_genotype_text,
  c.experimental_plate_id,
  c.experimental_slot_id,
  c.plate_index,
  c.slot_index,
  c.slot_index_global,
  c.data_location,

  r.imaging_roi_id,
  r.roi_index,
  r.roi_name,
  r.data_path,
  r.plate_code,
  r.slot_label,
  r.fish_code,
  r.fish_nickname,
  r.birthday,
  r.genetic_background,

  r.genotype_pretty,
  r.genotype_base_codes,
  r.genotype_alleles_pretty,
  r.genotype_marker_fluors,
  r.genotype_marker_tags,

  r.treat_code,
  r.treat_text,
  r.treatment_plasmid_base_codes,
  r.treatment_rna_base_codes,
  r.treatment_dye_base_codes,
  r.treatment_marker_fluor_codes,
  r.treatment_marker_tag_codes

FROM public.v_imaging_clutches_rois AS r
JOIN public.clutches AS c
  ON c.id = r.clutch_id
WHERE {where_sql}
ORDER BY
  c.clutch_code,
  c.clutch_date,
  r.experimental_plate_id,
  r.experimental_slot_id,
  r.roi_index
LIMIT :lim
""")

with get_engine().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} clutch→ROI row(s) from v_imaging_clutches_rois (limit {lim})")

if df.empty:
    st.info("No clutch/ROI chains matched the current filters.")
    st.stop()

# ---- add selection column ----------------------------------------------------
ro = df.copy()
ro.insert(0, "✓ Select", False)

column_config = {
    "clutch_code":                     st.column_config.TextColumn("Clutch", disabled=True),
    "clutch_date":                     st.column_config.DateColumn("Clutch date", disabled=True),
    "date_born":                       st.column_config.DateColumn("Date born", disabled=True),
    "zf_female_genotype_text":         st.column_config.TextColumn("Female genotype (sheet)", disabled=True),
    "zf_male_genotype_text":           st.column_config.TextColumn("Male genotype (sheet)", disabled=True),
    "experimental_plate_id":           st.column_config.TextColumn("Exp plate ID", disabled=True),
    "experimental_slot_id":            st.column_config.TextColumn("Exp slot ID", disabled=True),
    "plate_index":                     st.column_config.NumberColumn("Plate idx", disabled=True),
    "slot_index":                      st.column_config.NumberColumn("Slot idx", disabled=True),
    "slot_index_global":               st.column_config.NumberColumn("Global slot idx", disabled=True),
    "data_location":                   st.column_config.TextColumn("Data location (sheet)", disabled=True),

    "imaging_roi_id":                  st.column_config.TextColumn("ROI ID", disabled=True),
    "roi_index":                       st.column_config.NumberColumn("ROI #", disabled=True),
    "roi_name":                        st.column_config.TextColumn("ROI name", disabled=True),
    "data_path":                       st.column_config.TextColumn("Data path", disabled=True),
    "plate_code":                      st.column_config.TextColumn("Plate code", disabled=True),
    "slot_label":                      st.column_config.TextColumn("Slot label", disabled=True),
    "fish_code":                       st.column_config.TextColumn("Fish code", disabled=True),
    "fish_nickname":                   st.column_config.TextColumn("Fish nickname", disabled=True),
    "birthday":                        st.column_config.DateColumn("Fish DOB", disabled=True),
    "genetic_background":              st.column_config.TextColumn("Background", disabled=True),

    "genotype_pretty":                 st.column_config.TextColumn("Genotype (view)", disabled=True),
    "genotype_base_codes":             st.column_config.TextColumn("Genotype codes", disabled=True),
    "genotype_alleles_pretty":         st.column_config.TextColumn("Genotype alleles", disabled=True),
    "genotype_marker_fluors":          st.column_config.TextColumn("Genotype markers (fluors)", disabled=True),
    "genotype_marker_tags":            st.\