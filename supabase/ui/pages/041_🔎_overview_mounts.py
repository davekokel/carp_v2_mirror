from __future__ import annotations

import os, sys
from pathlib import Path
import io
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ────────────────────────── Path bootstrap ──────────────────────────
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Overview — Bruker Mounts", page_icon="🔎", layout="wide")
st.title("🔎 Overview — Bruker Mounts")

# ────────────────────────── DB / engine ─────────────────────────────
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set")
    st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

# Badge
from sqlalchemy import text as _text
try:
    host = (getattr(getattr(eng, "url", None), "host", None) or os.getenv("PGHOST", "") or "(unknown)")
    with eng.begin() as _cx:
        who = _cx.execute(_text("select current_user")).scalar() or ""
    st.caption(f"DB: {host} • user={who}")
except Exception:
    pass

# ────────────────────────── Helpers ─────────────────────────────────
def _one_checked(df: pd.DataFrame, check_col: str) -> pd.Series | None:
    if check_col not in df.columns:
        return None
    checked = df.index[df[check_col] == True].tolist()
    return df.loc[checked[0]] if len(checked) == 1 else None

def _ci_id_col(cx) -> str:
    """Return 'id' if present, else 'id_uuid' (for clutch_instances)."""
    has_id = bool(cx.execute(text("""
        select 1 from information_schema.columns
        where table_schema='public' and table_name='clutch_instances' and column_name='id'
    """)).first())
    if has_id:
        return "id"
    has_uuid = bool(cx.execute(text("""
        select 1 from information_schema.columns
        where table_schema='public' and table_name='clutch_instances' and column_name='id_uuid'
    """)).first())
    return "id_uuid" if has_uuid else "id"  # default back to id

# ────────────────────────── Day filter ──────────────────────────────
st.markdown("### Pick a day")
day = st.date_input("Mount date", value=dt.date.today())
if not day:
    st.info("Pick a date to view mounts.")
    st.stop()

# ────────────────────────── Load + enrich ───────────────────────────
with eng.begin() as cx:
    id_col = _ci_id_col(cx)

    # Base mounts for day; compute mount_code inline (column may not exist)
    df = pd.read_sql(
        text(f"""
            with base as (
              select
                selection_id,
                mount_date, mount_time,
                n_top, n_bottom, orientation,
                created_at, created_by
              from public.bruker_mounts
              where mount_date = :d
            )
            select
              'BRUKER ' || to_char(b.mount_date, 'YYYY-MM-DD') || ' #' ||
              row_number() over (
                partition by b.mount_date
                order by b.mount_time nulls last, b.created_at
              )                              as mount_code,
              b.selection_id::text           as selection_id,
              b.mount_date, b.mount_time,
              b.n_top, b.n_bottom, b.orientation,
              b.created_at, b.created_by
            from base b
            order by b.created_at desc
        """),
        cx, params={"d": day}
    )

    # Join selection label and cross_instance_id (robust to id/id_uuid)
    df_sel = pd.read_sql(
        text(f"""
            select
              {id_col}::text  as selection_id,
              label           as selection_label,
              cross_instance_id
            from public.clutch_instances
        """), cx
    )

    # Join runs for run code
    df_runs = pd.read_sql(
        text("""
            select
              cross_instance_id,
              cross_run_code,
              cross_date::date as run_date,
              mother_tank_label, father_tank_label
            from public.vw_cross_runs_overview
        """), cx
    )

# Left joins to enrich
if not df.empty:
    df = df.merge(df_sel, on="selection_id", how="left")
    df = df.merge(df_runs, on="cross_instance_id", how="left")

# ────────────────────────── Grid with checkboxes ────────────────────
st.markdown("### Mounts on selected day")
if df.empty:
    st.info("No mounts found for the selected day.")
    st.stop()

# Keep stable ordering and visible columns
columns_order = [
    "mount_code",
    "mount_date", "mount_time",
    "selection_label", "cross_run_code",
    "n_top", "n_bottom", "orientation",
    "created_at", "created_by",
]
# Ensure columns exist and order them
visible = [c for c in columns_order if c in df.columns]
grid_df = df[visible].copy()

# Inject checkbox column
grid_df.insert(0, "✓ Select", False)

# Render
editor = st.data_editor(
    grid_df,
    hide_index=True,
    use_container_width=True,
    column_order=["✓ Select"] + visible,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
    key="mounts_overview_editor",
)

# Persist in session (optional pattern)
st.session_state["_mounts_overview_table"] = editor.copy()

# Selection helpers
cA, cB, cC = st.columns([1, 1, 4])
with cA:
    if st.button("Select all"):
        st.session_state["_mounts_overview_table"]["✓ Select"] = True
        editor = st.session_state["_mounts_overview_table"]
with cB:
    if st.button("Clear"):
        st.session_state["_mounts_overview_table"]["✓ Select"] = False
        editor = st.session_state["_mounts_overview_table"]

selected_rows = editor[editor["✓ Select"] == True].copy()

st.caption(f"{len(editor)} row(s) • {len(selected_rows)} selected")

# ────────────────────────── PDF report for selected rows ────────────
st.markdown("### Print PDF report")
st.caption("Generates a simple label-style summary for the selected mounts.")

def _render_pdf_from_rows(rows: pd.DataFrame) -> bytes:
    # Minimal PDF via reportlab
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    def line(y, txt):
        c.setFont("Helvetica", 10)
        c.drawString(0.8*inch, y, txt)

    # Make one section per mount
    for _, r in rows.iterrows():
        y = H - 1.0*inch
        # Header
        c.setFont("Helvetica-Bold", 14)
        c.drawString(0.8*inch, y, f"{str(r.get('mount_code',''))}")
        y -= 0.3*inch

        # Body lines
        c.setFont("Helvetica", 10)
        items = [
            ("Date",        str(r.get("mount_date",""))),
            ("Time",        str(r.get("mount_time",""))),
            ("Selection",   str(r.get("selection_label",""))),
            ("Run",         str(r.get("cross_run_code",""))),
            ("Orientation", str(r.get("orientation",""))),
            ("Top/Bottom",  f"{str(r.get('n_top',''))} / {str(r.get('n_bottom',''))}"),
            ("Created by",  str(r.get("created_by",""))),
            ("Created at",  str(r.get("created_at",""))),
        ]
        for label, val in items:
            line(y, f"{label}: {val}")
            y -= 0.22*inch

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()

# Enable button when at least one row selected
if selected_rows.empty:
    st.button("Download PDF of selected", disabled=True)
else:
    # Reorder to visible columns + keep mount_code first in the PDF
    pdf_cols = ["mount_code","mount_date","mount_time","selection_label","cross_run_code",
                "orientation","n_top","n_bottom","created_by","created_at"]
    pdf_view = selected_rows[[c for c in pdf_cols if c in selected_rows.columns]].copy()
    pdf_bytes = _render_pdf_from_rows(pdf_view)
    st.download_button(
        "Download PDF of selected",
        data=pdf_bytes,
        file_name=f"bruker_mounts_{day.isoformat()}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )