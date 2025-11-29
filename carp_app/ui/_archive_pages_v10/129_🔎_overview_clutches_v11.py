from __future__ import annotations

import os
import pathlib
import sys
from typing import Optional, Dict, Any, List

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
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — v11 Overview: Clutches (genotype + treatment)",
    page_icon="🐣",
    layout="wide",
)

st.title("🐣 v11 Overview — Clutches (genotype + treatment)")


# ───────── engine (cached) ─────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return get_engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── filters ─────────
with st.form("clutch_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Search (clutch / genotype / genotype code / treatment)",
            "",
        )
    with c2:
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


# ───────── query v11_clutch_star ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  clutch_code           ILIKE :ql"
        " OR genotype_pretty     ILIKE :ql"
        " OR genotype_v11_code   ILIKE :ql"
        " OR genotype_v11_basecodes ILIKE :ql"
        " OR treat_codes         ILIKE :ql"
        " OR treat_basecodes     ILIKE :ql"
        ")"
    )

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      clutch_code,
      clutch_date,
      n_imaging_slots,
      n_rois,

      genotype_base_codes,
      genotype_v11_code,
      genotype_v11_basecodes,
      genotype_pretty,

      treat_codes,
      treat_basecodes

    FROM public.v11_clutch_star
    WHERE {where_sql}
    ORDER BY clutch_date, clutch_code
    LIMIT :lim;
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)


df_display = df.copy().fillna("")

st.caption(f"{len(df_display)} clutch row(s)")


# ───────── top grid ─────────
if df_display.empty:
    st.info("No clutches matched filters.")
    st.stop()

view = df_display.copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    key="v11_clutch_overview_table",
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "clutch_code",
        "clutch_date",
        "n_imaging_slots",
        "n_rois",

        "genotype_base_codes",
        "genotype_v11_code",
        "genotype_v11_basecodes",
        "genotype_pretty",

        "treat_codes",
        "treat_basecodes",
    ],
    column_config={
        "✓ Select":            st.column_config.CheckboxColumn("✓"),
        "clutch_code":         st.column_config.TextColumn("Clutch", disabled=True),
        "clutch_date":         st.column_config.DateColumn("Date", disabled=True),
        "n_imaging_slots":     st.column_config.NumberColumn("# slots", disabled=True),
        "n_rois":              st.column_config.NumberColumn("# ROIs", disabled=True),

        "genotype_base_codes":     st.column_config.TextColumn("Geno (raw Tg codes)", disabled=True),
        "genotype_v11_code":       st.column_config.TextColumn("Genotype Code", disabled=True),
        "genotype_v11_basecodes":  st.column_config.TextColumn("Genotype Basecodes", disabled=True),
        "genotype_pretty":         st.column_config.TextColumn("Genotype Pretty", disabled=True),

        "treat_codes":        st.column_config.TextColumn("Treatment Code(s)", disabled=True),
        "treat_basecodes":    st.column_config.TextColumn("Treatment Basecodes", disabled=True),
    },
)


# ───────── selected clutches ─────────
selected_clutches: List[str] = []
if isinstance(grid, pd.DataFrame):
    mask = grid["✓ Select"] == True
    selected_clutches = (
        grid.loc[mask, "clutch_code"]
        .dropna()
        .astype(str)
        .tolist()
    )


# ───────── ROI drill-down ─────────
st.divider()
st.subheader("Imaging ROIs for selected clutch(es)")

if not selected_clutches:
    st.caption("Select one or more clutches above.")
else:
    st.caption(f"{len(selected_clutches)} selected: {', '.join(selected_clutches)}")

    sql_rois = text("""
        SELECT
          clutch_code,
          plate_code,
          experiment_date,
          slot_label,
          slot_index,
          roi_code,
          roi_index,
          roi_note_anatomy,
          roi_path,
          fish_code,
          fish_genotype_pretty,
          tank_code,
          tank_status
        FROM public.v11_imaging_roi_star
        WHERE clutch_code = ANY(:codes)
        ORDER BY clutch_code, plate_code, slot_label, roi_index;
    """)

    with _eng().begin() as cx:
        df_rois = pd.read_sql(sql_rois, cx, params={"codes": selected_clutches})

    if df_rois.empty:
        st.info("No ROIs found.")
    else:
        df_rois_disp = df_rois.fillna("")
        st.data_editor(
            df_rois_disp,
            key="v11_clutch_rois_detail",
            hide_index=True,
            width="stretch",
            num_rows="fixed",
        )

        st.download_button(
            "⬇︎ Download ROIs (CSV)",
            data=df_rois_disp.to_csv(index=False).encode("utf-8"),
            file_name="v11_clutch_rois_selected.csv",
            type="secondary",
            mime="text/csv",
        )


# ───────── export full table ─────────
st.divider()
st.download_button(
    "⬇︎ Download clutches overview (CSV)",
    data=df_display.to_csv(index=False).encode("utf-8"),
    file_name="v11_clutches_overview.csv",
    type="secondary",
    mime="text/csv",
)