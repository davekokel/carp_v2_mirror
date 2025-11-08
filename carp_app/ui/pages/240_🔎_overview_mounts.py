# =============================================================================
# 024_🔎_overview_plates.py — Drill-down plates (summary + treated clutches + layout)
# Top grid: plates with summary stats (counts, orientation mode), searchable
# Drill-down per plate: treated clutch summary + full well layout + CSV export
# =============================================================================
from __future__ import annotations

import os, sys, pathlib
from typing import Optional, Set, Tuple, List
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── sys.path prime ────────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── auth gates ────────────────────────────────────────────────────────────────
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# ── app libs ─────────────────────────────────────────────────────────────────
from carp_app.ui.lib.app_ctx import get_engine as _create_engine
from carp_app.lib.time import utc_today

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="CARP — 🔎 Overview Plates (drill-down)", page_icon="🔎", layout="wide")
st.title("🔎 Overview Mounts")  # keep sidebar label stable

# ── engine cache ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _eng_cached() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def eng() -> Engine:
    return _eng_cached()

# ── helpers ──────────────────────────────────────────────────────────────────
def _exists_view(qname: str) -> bool:
    sch, name = qname.split(".", 1)
    sql = text("""
      SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n
      UNION ALL
      SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n
      LIMIT 1
    """)
    with eng().begin() as cx:
        return cx.execute(sql, {"s": sch, "n": name}).first() is not None

def _exists_table(qname: str) -> bool:
    sch, name = qname.split(".", 1)
    sql = text("""
      SELECT 1 FROM information_schema.tables
      WHERE table_schema=:s AND table_name=:n
      LIMIT 1
    """)
    with eng().begin() as cx:
        return cx.execute(sql, {"s": sch, "n": name}).first() is not None

V_LAYOUT   = "public.v_plate_layout"
T_PLATES   = "public.plates"
T_SLOTS    = "public.plate_slots"          # used only to check presence
V_TCLUTCH  = "public.v_treated_clutches"   # optional, for tx→genotype context
V_CI       = "public.v_clutch_instances"   # optional, if you want extra context

# ── queries ──────────────────────────────────────────────────────────────────
def _plates_for_day(day: Optional[pd.Timestamp]) -> pd.DataFrame:
    """
    Returns one row per plate (basic header). If day is given, filters by DATE(created_at)=day.
    """
    if not _exists_table(T_PLATES):
        return pd.DataFrame(columns=["plate_code","plate_name","format_code","created_by","created_at"])
    params = {}
    if day is not None:
        sql = text(f"""
          SELECT plate_code, plate_name, format_code, created_by, created_at
          FROM {T_PLATES}
          WHERE DATE(created_at) = :d
          ORDER BY created_at DESC NULLS LAST, plate_code
        """)
        params["d"] = pd.Timestamp(day).date()
    else:
        sql = text(f"""
          SELECT plate_code, plate_name, format_code, created_by, created_at
          FROM {T_PLATES}
          ORDER BY created_at DESC NULLS LAST, plate_code
          LIMIT 200
        """)
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes("object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _layout_for_plate(plate_code: str) -> pd.DataFrame:
    """
    Load per-well layout for a plate from v_plate_layout.
    """
    if not _exists_view(V_LAYOUT):
        return pd.DataFrame(columns=["well_label","treated_clutch_code","orientation"])
    sql = text(f"""
      SELECT plate_code, plate_name, format_code, n_rows, n_cols,
             row_idx, col_idx, row_letter, well_label,
             treated_clutch_id, treated_clutch_code, orientation, created_at
      FROM {V_LAYOUT}
      WHERE plate_code = :p
      ORDER BY row_idx, col_idx
    """)
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"p": plate_code})
    for c in df.select_dtypes("object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _plate_summary_from_layout(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize a single-plate layout DF into a one-row summary:
    - n_wells, n_filled, n_groups
    - distinct treated_clutch_code list
    - orientation_mode
    """
    if df.empty:
        return pd.DataFrame([{
            "n_wells": 0, "n_filled": 0, "n_groups": 0,
            "treated_groups": "", "orientation_mode": ""
        }])
    n_wells  = df.shape[0]
    filled   = df.loc[df["treated_clutch_code"] != ""]
    n_filled = filled.shape[0]
    codes = filled["treated_clutch_code"].unique().tolist()
    n_groups = len(codes)
    treated_groups = ", ".join(codes)

    # orientation mode (most frequent non-empty)
    orient_counts = df.loc[df["orientation"] != "", "orientation"].value_counts()
    orientation_mode = orient_counts.index[0] if not orient_counts.empty else ""

    return pd.DataFrame([{
        "n_wells": n_wells,
        "n_filled": n_filled,
        "n_groups": n_groups,
        "treated_groups": treated_groups,
        "orientation_mode": orientation_mode
    }])

def _treated_clutch_details(plate_layout: pd.DataFrame) -> pd.DataFrame:
    """
    For a plate, return per-treated_clutch_code details using v_treated_clutches when present.
    """
    codes = plate_layout.loc[plate_layout["treated_clutch_code"] != "", "treated_clutch_code"] \
                        .dropna().astype(str).unique().tolist()
    if not codes:
        return pd.DataFrame(columns=["treated_clutch_code","clutch_code","offspring_genotype","tx_to_genotype"])
    if not _exists_view(V_TCLUTCH):
        # minimal fallback
        return pd.DataFrame({"treated_clutch_code": codes})

    sql = text(f"""
      SELECT treated_clutch_code,
             clutch_code,
             COALESCE(clutch_genotype_pretty,'')    AS offspring_genotype,
             COALESCE(treatment_genotype_group,'')  AS tx_to_genotype
      FROM {V_TCLUTCH}
      WHERE treated_clutch_code = ANY(:codes)
      ORDER BY treated_clutch_code
    """)
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    for c in df.select_dtypes("object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

# ── filters ──────────────────────────────────────────────────────────────────
today = utc_today()
with st.form("filters"):
    c1, c2 = st.columns([1, 2])
    with c1:
        day = st.date_input("Day", value=today)
    with c2:
        q = st.text_input("Search (plate/format/group/geno contains)", value="")
    submitted = st.form_submit_button("Apply", width="stretch")

# ── load plates (header) ─────────────────────────────────────────────────────
plates = _plates_for_day(day)

if q.strip():
    _q = q.strip().lower()
    plates = plates[
        plates["plate_code"].fillna("").str.lower().str.contains(_q) |
        plates["format_code"].fillna("").str.lower().str.contains(_q) |
        plates["plate_name"].fillna("").str.lower().str.contains(_q)
    ]

if plates.empty:
    st.info("No plates found for this filter.")
    st.stop()

# Checkbox table of plates
grid = plates.copy()
grid.insert(0, "✓ Select", False)
picker = st.data_editor(
    grid,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config={
        "✓ Select":  st.column_config.CheckboxColumn("✓", default=False),
        "created_at": st.column_config.DatetimeColumn("created_at", format="YYYY-MM-DD HH:mm"),
    },
    key="overview_plates_pick_v1",
)

sel_series = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False)
selected = plates[sel_series].reset_index(drop=True)

st.divider()
st.subheader("Selected plate(s)")

if selected.empty:
    st.info("Select one or more plates above to view details.")
    st.stop()

for _, prow in selected.iterrows():
    pcode = str(prow["plate_code"])
    st.markdown(f"### Plate **{pcode}** — {prow['format_code']}")

    layout_df = _layout_for_plate(pcode)
    if layout_df.empty:
        st.info("No layout for this plate (unexpected).")
        continue

    # summary
    summary_df = _plate_summary_from_layout(layout_df)
    cA, cB = st.columns([1,1])
    with cA:
        info = pd.DataFrame([{
            "plate_name": str(prow.get("plate_name") or ""),
            "format_code": str(prow.get("format_code") or ""),
            "created_by": str(prow.get("created_by") or ""),
            "created_at": prow.get("created_at"),
        }])
        st.markdown("**Plate summary**")
        st.dataframe(info, hide_index=True, use_container_width=True)
    with cB:
        st.markdown("**Fill / groups / orientation**")
        st.dataframe(summary_df, hide_index=True, use_container_width=True)

    # treated clutch details
    tdf = _treated_clutch_details(layout_df)
    st.markdown("**Treated clutch summary**")
    if tdf.empty:
        st.caption("No treated groups on this plate.")
    else:
        st.dataframe(tdf, hide_index=True, use_container_width=True)

    # layout (wells)
    st.markdown("**Plate layout (wells)**")
    st.dataframe(layout_df[["well_label","treated_clutch_code","orientation"]],
                 hide_index=True, use_container_width=True, height=260)

    # CSV export
    csv_df = layout_df[["plate_code","plate_name","format_code","well_label","treated_clutch_code","orientation"]].copy()
    st.download_button(
        "⬇︎ Download layout CSV",
        data=csv_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{pcode}_layout.csv",
        mime="text/csv",
        type="secondary",
        use_container_width=True
    )

    st.markdown("---")