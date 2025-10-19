from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os, io
from pathlib import Path
from datetime import date
from typing import List, Set

import pandas as pd
import streamlit as st
from sqlalchemy import text
from zoneinfo import ZoneInfo

from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()
from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

# ───────────────────────── bootstrap ─────────────────────────
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Overview — Bruker Mounts", page_icon="🔎", layout="wide")
st.title("🔎 Overview — Bruker Mounts")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

# Local day default (can be different from DB TZ)
APP_TZ = os.getenv("APP_TZ", "America/Los_Angeles")
LOCAL_TODAY = pd.Timestamp.now(tz=ZoneInfo(APP_TZ)).date()

# DB/TZ caption
try:
    with eng.begin() as cx:
        db_tz = cx.execute(text("select current_setting('TimeZone')")).scalar()
    st.caption(f"DB session TimeZone = {db_tz}")
except Exception:
    pass

# DB host/user caption
try:
    url = getattr(eng, "url", None)
    host = (getattr(url, "host", None) or os.getenv("PGHOST", "(unknown)"))
    with eng.begin() as cx:
        role = cx.execute(text("select current_setting('role', true)")).scalar()
        who  = cx.execute(text("select current_user")).scalar()
    st.caption(f"DB: {host} • role={role or 'default'} • user={who or ''}")
except Exception:
    pass

# ───────────────────────── helpers ─────────────────────────
def _load_mounts_for_day(d: date) -> pd.DataFrame:
    """
    Load Bruker mounts for a given day from public.bruker_mount.
    Uses a computed timestamp for proper sorting regardless of NULL time.
    """
    sql = text("""
      select
        bm.mount_code,
        bm.mount_date,
        bm.mount_time,
        bm.mount_orientation,
        bm.mount_top_n,
        bm.mount_bottom_n,
        bm.mount_notes,
        (bm.mount_date::timestamp + coalesce(bm.mount_time, time '00:00')) as mount_ts
      from public.bruker_mount bm
      where bm.mount_date = :d
      order by (bm.mount_date::timestamp + coalesce(bm.mount_time, time '00:00')) desc nulls last
    """)
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params={"d": d})

def _kpis(df: pd.DataFrame) -> None:
    total = len(df)
    embryos = int(df.get("mount_top_n", 0).fillna(0).sum() + df.get("mount_bottom_n", 0).fillna(0).sum())
    last_ts = df["mount_ts"].max() if "mount_ts" in df.columns and df["mount_ts"].notna().any() else None

    c1, c2, c3 = st.columns([1,1,1])
    c1.metric("Mounts", f"{total}")
    c2.metric("Embryos (top+bottom)", f"{embryos}")
    c3.metric("Last saved", f"{last_ts}" if pd.notna(last_ts) else "—")

# ───────────────────────── day picker ─────────────────────────
st.markdown("### Pick a day")
day = st.date_input("Day", value=LOCAL_TODAY, key="overview_mounts_day")

df = _load_mounts_for_day(day)

if df.empty:
    st.warning("No mounts found for the selected day.", icon="⚠️")
    st.stop()

# ───────────────────────── KPIs ─────────────────────────
_kpis(df)

# ───────────────────────── grid with selection ─────────────────────────
st.markdown("### Mounts for the selected day")

display_cols = [
    "mount_code",
    "mount_date","mount_time","mount_orientation",
    "mount_top_n","mount_bottom_n",
    "mount_notes",
]
present = [c for c in display_cols if c in df.columns]
view = df[present].copy()

# maintain checked set in session (use mount_code as selection key)
checked_key = "_overview_mounts_checked"
chk: Set[str] = st.session_state.get(checked_key, set())
if not isinstance(chk, set):
    chk = set(chk)

# add ✓ column
view.insert(0, "✓", view["mount_code"].isin(chk))

grid = st.data_editor(
    view,
    hide_index=True, use_container_width=True,
    column_order=["✓"] + present,
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False)},
    key="overview_mounts_editor",
)

# reconcile checked set
visible_codes = view["mount_code"].tolist()
edited_checked = grid["✓"].tolist()
new_checked_codes = {code for code, ok in zip(visible_codes, edited_checked) if ok}
chk = (chk - set(visible_codes)) | new_checked_codes
st.session_state[checked_key] = chk

lcol, rcol = st.columns([1,1])
with lcol:
    if st.button("Select all"):
        st.session_state[checked_key] |= set(visible_codes)
        st.rerun()
with rcol:
    if st.button("Clear"):
        st.session_state[checked_key] -= set(visible_codes)
        st.rerun()

chosen = df[df["mount_code"].isin(st.session_state[checked_key])].copy()

# ───────────────────────── PDF generation ─────────────────────────
st.markdown("### 📄 Download 1-page PDF")
if chosen.empty:
    st.caption("Select one or more mounts above to enable the PDF export.")
else:
    # Build a one-page landscape PDF with compact columns
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    PAGE_W, PAGE_H = landscape(letter)
    MARGIN = 36
    INNER_W = PAGE_W - 2 * MARGIN

    doc = SimpleDocTemplate(
        buf, pagesize=landscape(letter),
        topMargin=MARGIN, bottomMargin=MARGIN,
        leftMargin=MARGIN, rightMargin=MARGIN,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    body = styles["BodyText"]; body.fontName="Helvetica"; body.fontSize=7; body.leading=8; body.wordWrap="CJK"

    elements = []
    title = f"Bruker Mounts — {day.strftime('%Y-%m-%d')}"
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 8))

    pdf_cols = [
        "mount_code",
        "mount_date","mount_time","mount_orientation",
        "mount_top_n","mount_bottom_n","mount_notes",
    ]
    widths = [120, 70, 70, 110, 70, 90, 240]
    scale = INNER_W / sum(widths)
    if abs(scale - 1.0) > 0.02:
        widths = [w * scale for w in widths]

    texty = {"mount_code","mount_orientation","mount_notes"}
    present_pdf = [c for c in pdf_cols if c in chosen.columns]
    header = present_pdf[:]

    rows = []
    for _, r in chosen[present_pdf].iterrows():
        row = []
        for c in present_pdf:
            val = "" if pd.isna(r[c]) else str(r[c])
            row.append(Paragraph(val, body) if c in texty else val)
        rows.append(row)

    data = [header] + rows
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 8),
        ("GRID", (0,0), (-1,-1), 0.25, colors.black),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
    ]))

    elements.append(table)
    doc.build(elements); buf.seek(0)

    st.download_button(
        label="⬇️ Download 1-page PDF",
        data=buf,
        file_name=f"bruker_mounts_{day.strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )