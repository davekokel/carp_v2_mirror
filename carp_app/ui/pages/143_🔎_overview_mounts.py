# carp_app/ui/pages/240_🔎_overview_mounts.py
# 🔎 Overview — Plates (v11 imaging): browse imaging plates and well layouts

from __future__ import annotations

import sys, pathlib
from typing import Any, Dict, List, Tuple

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

eng = engine()

# --- auth / page --------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🔎 Overview: Plates",
    page_icon="🧫",
    layout="wide",
)
st.title("🔎 Overview — Plates (v11 imaging)")

with eng.begin() as cx:
    dbg = pd.read_sql(
        text("select current_database() db, inet_server_addr() host, current_user u"), cx
    )
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# --- imaging objects we read --------------------------------------------------
T_IMAGING_PLATES = "public.imaging_plates"
T_IMAGING_SLOTS  = "public.imaging_slots"
T_IMAGING_MEMB   = "public.imaging_clutch_memberships"
T_CLUTCHES       = "public.clutches"

# --- tiny helpers -------------------------------------------------------------
def _exists_table(qualified: str) -> bool:
    s, n = qualified.split(".", 1)
    with eng.begin() as cx:
        r = pd.read_sql(
            text(
                """
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema=:s AND table_name=:n
          LIMIT 1
        """
            ),
            cx,
            params={"s": s, "n": n},
        )
    return not r.empty

def _safe(cx, q: str | TextClause, p: Dict[str, Any] | None = None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

def _pivot(title: str, rows: List[Tuple[str, Any]]):
    dfp = pd.DataFrame(rows, columns=["Field", "Value"])
    st.markdown(f"**{title}**")
    st.dataframe(dfp, hide_index=True, use_container_width=True)

# --- guards -------------------------------------------------------------------
missing = []
for t in (T_IMAGING_PLATES, T_IMAGING_SLOTS, T_IMAGING_MEMB, T_CLUTCHES):
    if not _exists_table(t):
        missing.append(t)

if missing:
    st.error("Required object not found: " + ", ".join(missing))
    st.stop()

# --- loaders ------------------------------------------------------------------
def _list_imaging_plates(q: str, limit: int) -> pd.DataFrame:
    sql = text(
        f"""
      SELECT
        p.id::text                              AS plate_id,
        p.plate_code,
        p.experiment_date,
        COALESCE(p.scope_name, p.instrument,'') AS microscope_type,
        COALESCE(p.plate_note, p.notes,'')      AS plate_note,
        p.created_at
      FROM {T_IMAGING_PLATES} p
      WHERE (:q = '' OR
             p.plate_code                      ILIKE :ql OR
             COALESCE(p.scope_name,'')         ILIKE :ql OR
             COALESCE(p.instrument,'')         ILIKE :ql OR
             COALESCE(p.plate_note,'')         ILIKE :ql OR
             COALESCE(p.notes,'')              ILIKE :ql)
      ORDER BY p.experiment_date DESC NULLS LAST, p.plate_code
      LIMIT :lim
    """
    )
    with eng.begin() as cx:
        df = _safe(cx, sql, {"q": q or "", "ql": f"%{q or ''}%", "lim": int(limit)})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _layout_for_plate(plate_id: str) -> pd.DataFrame:
    """
    Build a layout for a given imaging plate:
    one row per imaging_slot, with clutch (if any) & orientation.
    """
    sql = text(
        f"""
      SELECT
        p.plate_code,
        p.experiment_date,
        COALESCE(p.scope_name, p.instrument,'') AS microscope_type,
        s.id::text                              AS slot_id,
        s.slot_label,
        s.well_row,
        s.well_col,
        COALESCE(s.orientation,'')             AS orientation,
        c.id::text                              AS clutch_id,
        COALESCE(c.clutch_code,'')             AS clutch_code
      FROM {T_IMAGING_SLOTS} s
      JOIN {T_IMAGING_PLATES} p ON p.id = s.plate_id
      LEFT JOIN {T_IMAGING_MEMB} m ON m.slot_id = s.id
      LEFT JOIN {T_CLUTCHES}      c ON c.id = m.clutch_id
      WHERE p.id = CAST(:pid AS uuid)
      ORDER BY s.well_row, s.well_col
    """
    )
    with eng.begin() as cx:
        df = _safe(cx, sql, {"pid": plate_id})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

# --- filters / picker ---------------------------------------------------------
with st.form("filters"):
    c1, c2 = st.columns([3, 1])
    qtxt = c1.text_input("Search plates (code / microscope / note)", value="")
    limit = int(c2.number_input("Limit", min_value=10, max_value=2000, value=500, step=50))
    st.form_submit_button("Apply", use_container_width=True)

plates = _list_imaging_plates(qtxt, limit)
if plates.empty:
    st.info("No imaging plates found."); st.stop()

# Show/choose plates
st.subheader("Imaging plates")
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
        "experiment_date": st.column_config.DateColumn("experiment_date", disabled=True),
        "microscope_type": st.column_config.TextColumn("microscope_type", disabled=True),
        "plate_note":      st.column_config.TextColumn("note", disabled=True, width="large"),
        "created_at":      st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key="imaging_plates_overview_grid_v1",
)

sel_mask = grid.get("✓ Select", pd.Series(False, index=grid.index)).fillna(False).astype(bool)
picked = grid[sel_mask].reset_index(drop=True)

if picked.empty:
    st.info("Select a plate above to view its layout."); st.stop()

plate_row = picked.iloc[0]
plate_id   = plate_row["plate_id"]
plate_code = plate_row["plate_code"]

# --- layout viewer ------------------------------------------------------------
layout_df = _layout_for_plate(plate_id)
if layout_df.empty:
    st.warning("No slots/layout rows for this plate.")
    st.stop()

st.subheader(f"Layout — {plate_code}")

meta = layout_df.iloc[0]
summary_rows = [
    ("plate_code",       meta.get("plate_code")),
    ("experiment_date",  meta.get("experiment_date")),
    ("microscope_type",  meta.get("microscope_type")),
]

_pivot("Plate summary", summary_rows)

# Pretty layout (slot, clutch, orientation)
st.markdown("**Slots**")
show_cols = ["slot_label", "clutch_code", "orientation", "well_row", "well_col"]
st.dataframe(layout_df[show_cols], hide_index=True, use_container_width=True)

# quick counts
counts = layout_df.assign(
    has_clutch=layout_df["clutch_code"].ne(""),
    has_orientation=layout_df["orientation"].ne(""),
)
st.markdown("**Counts**")
st.write(
    {
        "wells_total": int(layout_df.shape[0]),
        "wells_with_clutch": int(counts["has_clutch"].sum()),
        "wells_with_orientation": int(counts["has_orientation"].sum()),
    }
)