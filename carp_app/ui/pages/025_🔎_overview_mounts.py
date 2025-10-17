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
    sql = text("""
      select
        m.id::text                       as mount_id,
        m.mount_label,
        m.mount_code,
        m.mount_date,
        m.time_mounted,
        m.mounting_orientation,
        m.n_top, m.n_bottom,
        m.sample_id, m.mount_type, m.notes,
        m.created_at, m.created_by,
        ci.cross_run_code,
        cp.clutch_code,
        cp.planned_name      as clutch_name,
        cp.planned_nickname  as clutch_nickname
      from public.mounts m
      join public.cross_instances ci  on ci.id = m.cross_instance_id
      join public.planned_crosses pc  on pc.cross_id = ci.cross_id
      join public.clutch_plans cp     on cp.id = pc.clutch_id
      where m.mount_date = :d
      order by coalesce(m.time_mounted, m.mount_date::timestamptz, m.created_at) desc nulls last
    """)
    with eng.begin() as cx:
        # pass a real date object; no string, no cast needed
        return pd.read_sql(sql, cx, params={"d": d})

def _kpis(df: pd.DataFrame) -> None:
    total = len(df)
    embryos = int(df.get("n_top", 0).fillna(0).sum() + df.get("n_bottom", 0).fillna(0).sum())
    last_ts = None
    if "time_mounted" in df.columns and df["time_mounted"].notna().any():
        last_ts = df["time_mounted"].max()
    elif df["created_at"].notna().any():
        last_ts = df["created_at"].max()

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
    "mount_label",        # human label (MT-YYYY-MM-DD #N)
    "cross_run_code",
    "clutch_code",
    "clutch_name",
    "mount_date","time_mounted","mounting_orientation",
    "n_top","n_bottom",
    "sample_id","mount_type","notes",
    "created_by","created_at",
]
present = [c for c in display_cols if c in df.columns]
view = df[["mount_id"] + present].copy()

# maintain checked set in session
checked_key = "_overview_mounts_checked"
chk: Set[str] = st.session_state.get(checked_key, set())
if not isinstance(chk, set):
    chk = set(chk)
# add ✓ column
view.insert(1, "✓", view["mount_id"].isin(chk))

grid = st.data_editor(
    view.drop(columns=["mount_id"]),
    hide_index=True, use_container_width=True,
    column_order=["✓"] + present,
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False)},
    key="overview_mounts_editor",
)

# reconcile checked set
visible_ids = view["mount_id"].tolist()
edited_checked = grid["✓"].tolist()
new_checked_ids = {mid for mid, ok in zip(visible_ids, edited_checked) if ok}
chk = (chk - set(visible_ids)) | new_checked_ids
st.session_state[checked_key] = chk

lcol, rcol = st.columns([1,1])
with lcol:
    if st.button("Select all"):
        st.session_state[checked_key] |= set(visible_ids)
        st.rerun()
with rcol:
    if st.button("Clear"):
        st.session_state[checked_key] -= set(visible_ids)
        st.rerun()

chosen = df[df["mount_id"].isin(st.session_state[checked_key])].copy()

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
        "mount_label", "cross_run_code", "clutch_code",
        "clutch_name", "n_top", "n_bottom",
        "mounting_orientation", "sample_id", "mount_type", "notes",
    ]
    widths = [105, 90, 80, 150, 40, 50, 90, 120, 70, 160]
    scale = INNER_W / sum(widths)
    if abs(scale - 1.0) > 0.02:
        widths = [w * scale for w in widths]

    texty = {"mount_label","cross_run_code","clutch_code","clutch_name","mounting_orientation","sample_id","mount_type","notes"}
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