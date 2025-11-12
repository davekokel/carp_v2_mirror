# carp_app/ui/pages/240_🔎_overview_mounts.py
# 🔎 Overview — Plates (formerly mounts): browse plates and view well layouts
from __future__ import annotations

import sys, pathlib
from typing import Any, Dict

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

# --- project wiring -----------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine

# --- auth / page --------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — 🔎 Overview: Plates", page_icon="🧫", layout="wide")
st.title("🔎 Overview — Plates")

with engine().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# --- objects we read ----------------------------------------------------------
T_PLATES   = "public.plates"
T_FORMATS  = "public.plate_formats"
V_LAYOUT   = "public.v_plate_layout"   # columns: plate_code, plate_nickname, format_code, n_rows, n_cols, ...

# --- tiny helpers -------------------------------------------------------------
def _exists_table(qualified: str) -> bool:
    s, n = qualified.split(".", 1)
    with engine().begin() as cx:
        r = pd.read_sql(text("""
          SELECT 1 FROM information_schema.tables
          WHERE table_schema=:s AND table_name=:n LIMIT 1
        """), cx, params={"s": s, "n": n})
    return not r.empty

def _exists_view(qualified: str) -> bool:
    s, n = qualified.split(".", 1)
    with engine().begin() as cx:
        r = pd.read_sql(text("""
          SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n
          UNION ALL
          SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n
          LIMIT 1
        """), cx, params={"s": s, "n": n})
    return not r.empty

def _safe(cx, q: str | TextClause, p: Dict[str, Any] | None = None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

# --- guards -------------------------------------------------------------------
missing = []
if not _exists_table(T_PLATES):  missing.append(T_PLATES)
if not _exists_table(T_FORMATS): missing.append(T_FORMATS)
if not _exists_view(V_LAYOUT):   missing.append(V_LAYOUT)
if missing:
    st.error("Required object not found: " + ", ".join(missing))
    st.stop()

# --- loaders ------------------------------------------------------------------
def _list_plates(q: str) -> pd.DataFrame:
    sql = text(f"""
      SELECT p.plate_code,
             COALESCE(p.nickname,'') AS plate_nickname,
             p.format_code,
             pf.n_rows, pf.n_cols,
             p.created_at
      FROM {T_PLATES} p
      LEFT JOIN {T_FORMATS} pf ON pf.code = p.format_code
      WHERE (:q = '' OR
             p.plate_code ILIKE :ql OR
             COALESCE(p.nickname,'') ILIKE :ql OR
             COALESCE(p.format_code,'') ILIKE :ql)
      ORDER BY p.created_at DESC NULLS LAST, p.plate_code
      LIMIT 1000
    """)
    with engine().begin() as cx:
        df = _safe(cx, sql, {"q": q or "", "ql": f"%{q or ''}%"})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _layout_for_plate(plate_code: str) -> pd.DataFrame:
    """
    NOTE: v_plate_layout exposes plate_nickname (NOT plate_name).
    """
    sql = text(f"""
      SELECT
        plate_code,
        COALESCE(plate_nickname,'') AS plate_nickname,
        format_code, n_rows, n_cols,
        row_idx, col_idx, row_letter, well_label,
        treated_clutch_id, treated_clutch_code,
        orientation, created_at
      FROM {V_LAYOUT}
      WHERE plate_code = :p
      ORDER BY row_idx, col_idx
    """)
    with engine().begin() as cx:
        df = _safe(cx, sql, {"p": plate_code})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

# --- filters / picker ---------------------------------------------------------
with st.form("filters"):
    c1, c2 = st.columns([3, 1])
    qtxt = c1.text_input("Search plates (code / nickname / format)", value="")
    limit = int(c2.number_input("Limit", min_value=10, max_value=2000, value=500, step=50))
    st.form_submit_button("Apply", use_container_width=True)

plates = _list_plates(qtxt)
if plates.empty:
    st.info("No plates found."); st.stop()

# Show/choose plates
st.subheader("Plates")
grid = plates.copy()
if "✓ Select" not in grid.columns:
    grid.insert(0, "✓ Select", False)

grid = st.data_editor(
    grid,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select":        st.column_config.CheckboxColumn("✓", default=False),
        "plate_code":      st.column_config.TextColumn("plate_code", disabled=True),
        "plate_nickname":  st.column_config.TextColumn("nickname", disabled=True),
        "format_code":     st.column_config.TextColumn("format", disabled=True),
        "n_rows":          st.column_config.NumberColumn("rows", disabled=True),
        "n_cols":          st.column_config.NumberColumn("cols", disabled=True),
        "created_at":      st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key="plates_overview_grid_v1",
)

sel = grid.get("✓ Select", pd.Series(False, index=grid.index)).fillna(False).astype(bool)
picked_codes = grid.loc[sel, "plate_code"].astype(str).tolist()

if not picked_codes:
    st.info("Select a plate above to view its layout."); st.stop()

# --- layout viewer ------------------------------------------------------------
pcode = picked_codes[0]
layout_df = _layout_for_plate(pcode)
if layout_df.empty:
    st.warning("No layout rows for this plate.")
    st.stop()

st.subheader(f"Layout — {pcode}")
meta = layout_df.iloc[0]
st.caption(f"{meta['plate_code']} • {meta['plate_nickname']} • {meta['format_code']} • {int(meta['n_rows'])}×{int(meta['n_cols'])}")

# Pretty layout (well, clutch, orientation)
show_cols = ["well_label", "treated_clutch_code", "orientation", "row_idx", "col_idx"]
st.dataframe(layout_df[show_cols], hide_index=True, use_container_width=True)

# Optional: quick counts
st.markdown("**Counts**")
counts = (
    layout_df.assign(
        has_code=layout_df["treated_clutch_code"].ne(""),
        has_ori=layout_df["orientation"].ne("")
    )
)
st.write({
    "wells_total": int(layout_df.shape[0]),
    "wells_with_code": int(counts["has_code"].sum()),
    "wells_with_orientation": int(counts["has_ori"].sum()),
})