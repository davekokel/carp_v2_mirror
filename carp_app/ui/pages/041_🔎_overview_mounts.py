from __future__ import annotations
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

import os
import sys
from pathlib import Path
import datetime as dt
import io
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from zoneinfo import ZoneInfo
APP_TZ = os.getenv("APP_TZ", "America/Los_Angeles")
LA_TODAY = dt.datetime.now(ZoneInfo(APP_TZ)).date()

# ────────────────────────── bootstrap ──────────────────────────
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Overview — Bruker Mounts", page_icon="🔎", layout="wide")
st.title("🔎 Overview — Bruker Mounts")

# ────────────────────────── engine / user ──────────────────────
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set")
    st.stop()

eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

try:
    from sqlalchemy import text as _text
    with eng.begin() as _cx:
        _tz = _cx.execute(_text("select current_setting('TimeZone')")).scalar()
    st.caption(f"DB session TimeZone = {_tz}")
except Exception:
    pass

from sqlalchemy import text as _text
user = ""
try:
    url = getattr(eng, "url", None)
    host = (getattr(url, "host", None) or os.getenv("PGHOST", "") or "(unknown)")
    with eng.begin() as cx:
        role = cx.execute(_text("select current_setting('role', true)")).scalar()
        who  = cx.execute(_text("select current_user")).scalar()
    user = who or ""
    st.caption(f"DB: {host} • role={role or 'default'} • user={user}")
except Exception:
    pass

# ────────────────────────── helpers ────────────────────────────
def _banner_warn(msg: str):
    st.warning(msg, icon="⚠️")

# ────────────────────────── day picker ─────────────────────────
# --- Pick a day ---
st.markdown("### Pick a day")
day = st.date_input("Day", value=LA_TODAY, key="overview_mounts_day")  # unique key

# --- Query mounts (use enriched view; cast uuid/text to avoid Arrow issues) ---
from sqlalchemy import text

with eng.begin() as cx:
    sql = text("""
        select
          mount_code,
          selection_id::text     as selection_id,
          mount_date, mount_time,
          n_top, n_bottom, orientation,
          created_at, created_by
        from public.vw_bruker_mounts_enriched
        where mount_date = cast(:d as date)
        order by created_at desc
    """)
    df = pd.read_sql(sql, cx, params={"d": str(day)})

if df.empty:
    _banner_warn("No mounts found for the selected day.")
else:
    st.dataframe(df, width='stretch')

# ────────────────────────── query mounts with live annotations ─────────────
with eng.begin() as cx:
    df = pd.read_sql(
        text("""
          with mounts as (
            select *
            from public.bruker_mounts
            where mount_date = :d
          )
          select
            m.id                                     as mount_id,          -- stable key
            'BRUKER '||to_char(m.mount_date,'YYYY-MM-DD')||' #'||
            row_number() over (
              partition by m.mount_date
              order by m.mount_time nulls last, m.created_at
            )                                         as mount_code,
            m.mount_time,
            ci.label                                  as selection_label,
            r.cross_run_code,
            c.name                                    as clutch_name,
            c.nickname                                as clutch_nickname,
            coalesce(trim(
              concat_ws(' ',
                case when ci.red_intensity   <> '' then 'red='   || ci.red_intensity   end,
                case when ci.green_intensity <> '' then 'green=' || ci.green_intensity end,
                case when ci.notes           <> '' then 'note='  || ci.notes          end
              )
            ), '')                                    as annotations,
            m.n_top, m.n_bottom, m.orientation,
            m.created_by, m.created_at
          from mounts m
          left join public.clutch_instances ci
            on ci.id = m.selection_id                 -- both uuid; no casts needed
          left join public.vw_cross_runs_overview r
            on r.cross_instance_id = ci.cross_instance_id
          left join public.v_cross_concepts_overview c
            on c.mom_code = r.mom_code and c.dad_code = r.dad_code
          order by m.created_at desc
        """),
        cx,
        params={"d": day},
    )

if df.empty:
    _banner_warn("No mounts found for the selected day.")
    st.stop()

# ────────────────────────── grid + selection (stable) ───────────────────
st.markdown("### Mounts on selected day")

# Columns shown in the grid (keep mount_id hidden)
grid_cols = [
    "mount_code",
    "mount_time",
    "selection_label",
    "cross_run_code",
    "clutch_name",
    "clutch_nickname",
    "annotations",
    "n_top",
    "n_bottom",
    "orientation",
    "created_by",
    "created_at",
]
present = [c for c in grid_cols if c in df.columns]
df_view = df[["mount_id"] + present].copy()

# Keep a stable set of checked mount_ids in session
checked_key = "_overview_mounts_checked"
if checked_key not in st.session_state:
    st.session_state[checked_key] = set()
# ensure it's a set even after session deserialization
if not isinstance(st.session_state[checked_key], set):
    st.session_state[checked_key] = set(st.session_state[checked_key])

# Build the display frame with ✓ from the set
df_view.insert(1, "✓", df_view["mount_id"].isin(st.session_state[checked_key]))

grid_edit = st.data_editor(
    df_view.drop(columns=["mount_id"]),
    hide_index=True,
    use_container_width=True,
    column_order=["✓"] + present,
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False)},
    key="overview_mounts_editor",
)

# Read user edits back into the set (only for rows currently visible)
visible_ids = df_view["mount_id"].tolist()
edited_checked = grid_edit["✓"].tolist()
new_checked_ids = {mid for mid, ok in zip(visible_ids, edited_checked) if ok}

# Update the session set for visible rows only
before = st.session_state[checked_key]
after = (before - set(visible_ids)) | new_checked_ids
st.session_state[checked_key] = after

left, right = st.columns([1, 1])
with left:
    if st.button("Select all"):
        st.session_state[checked_key] |= set(visible_ids)
        st.rerun()
with right:
    if st.button("Clear"):
        st.session_state[checked_key] -= set(visible_ids)
        st.rerun()

# Subset for PDF (use the stable set)
chosen = df[df["mount_id"].isin(st.session_state[checked_key])].copy()

# ────────────────────────── PDF generation ─────────────────────
st.markdown("### 📄 Download PDF report")

if chosen.empty:
    st.caption("Select one or more mounts above to enable the PDF export.")
else:
    buf = io.BytesIO()

    # Landscape Letter page
    PAGE_W, PAGE_H = landscape(letter)
    MARGIN = 36
    INNER_W = PAGE_W - 2 * MARGIN

    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(letter),
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]

    # Smaller body style for dense table
    body = styles["BodyText"]
    body.fontName = "Helvetica"
    body.fontSize = 7
    body.leading = 8
    body.wordWrap = "CJK"  # allow wrapping anywhere (best effort for tight cells)

    elements = []
    title = f"Bruker Mounts — {day.strftime('%Y-%m-%d')}"
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 10))

    # Report table columns (as requested: remove cross_run_code, mount_time, clutch_nickname)
    pdf_cols = [
        "mount_code", "selection_label", "clutch_name",
        "annotations", "n_top", "n_bottom", "orientation", "created_by"
    ]

    # Fixed widths; cut annotations to half the previous (e.g., 190 → ~95)
    # Sum ≈ 720 (will be scaled to INNER_W if needed)
    col_widths = [
        105,   # mount_code
        120,   # selection_label
        140,   # clutch_name
         95,   # annotations (wrapped, half previous)
         35,   # n_top
         45,   # n_bottom
         70,   # orientation
         70,   # created_by
    ]
    scale = INNER_W / sum(col_widths)
    if abs(scale - 1.0) > 0.02:
        col_widths = [w * scale for w in col_widths]

    # Build data with wrapped Paragraphs for texty fields
    texty = {"mount_code", "selection_label", "clutch_name", "annotations", "orientation", "created_by"}
    present_pdf = [c for c in pdf_cols if c in chosen.columns]
    header = present_pdf[:]

    rows = []
    for _, r in chosen[present_pdf].iterrows():
        row = []
        for c in present_pdf:
            val = "" if pd.isna(r[c]) else str(r[c])
            if c in texty:
                row.append(Paragraph(val, body))
            else:
                row.append(val)
        rows.append(row)

    data = [header] + rows

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 8),
        ("GRID", (0,0), (-1,-1), 0.25, colors.black),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
    ]))

    # If you must hard cap to one page, uncomment the following and tune cap_rows:
    # cap_rows = 22
    # if len(rows) > cap_rows:
    #     data = [header] + rows[:cap_rows]
    #     table = Table(data, colWidths=col_widths, repeatRows=1)
    #     table.setStyle(TableStyle([
    #         ("BACKGROUND", (0,0), (-1,0), colors.grey),
    #         ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
    #         ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    #         ("FONTSIZE", (0,0), (-1,0), 8),
    #         ("GRID", (0,0), (-1,-1), 0.25, colors.black),
    #         ("VALIGN", (0,0), (-1,-1), "TOP"),
    #         ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
    #     ]))

    elements.append(table)
    doc.build(elements)
    buf.seek(0)

    st.download_button(
        label="⬇️ Download 1-page PDF",
        data=buf,
        file_name=f"bruker_mounts_{day.strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
