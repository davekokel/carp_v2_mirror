from __future__ import annotations

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
st.markdown("### Pick a day")
day = st.date_input("Day", value=dt.date.today())

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

# ────────────────────────── grid + selection ───────────────────
st.markdown("### Mounts on selected day")

cols_order = [
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
]
present = [c for c in cols_order if c in df.columns]
df = df[present].copy()

# Checkbox selection
key_grid = "_overview_mounts_grid"
if key_grid not in st.session_state:
    t = df.copy()
    t.insert(0, "✓", False)
    st.session_state[key_grid] = t
else:
    base = st.session_state[key_grid]
    if "mount_code" in df.columns and "mount_time" in df.columns:
        base = base.set_index(["mount_code", "mount_time"])
        now = df.set_index(["mount_code", "mount_time"])
        for idx in now.index:
            if idx not in base.index:
                base.loc[idx] = [False] + now.loc[idx].to_list()
        base = base.loc[now.index]
        st.session_state[key_grid] = base.reset_index()
    else:
        st.session_state[key_grid] = df.copy().assign(**{"✓": False}).loc[:, ["✓"] + list(df.columns)]

grid_edit = st.data_editor(
    st.session_state[key_grid],
    hide_index=True,
    use_container_width=True,
    column_order=["✓"] + list(df.columns),
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False)},
    key="overview_mounts_editor",
)
st.session_state[key_grid].loc[grid_edit.index, "✓"] = grid_edit["✓"]

left, right = st.columns([1, 1])
with left:
    if st.button("Select all"):
        st.session_state[key_grid]["✓"] = True
        st.experimental_rerun()
with right:
    if st.button("Clear"):
        st.session_state[key_grid]["✓"] = False
        st.experimental_rerun()

chosen = st.session_state[key_grid].loc[st.session_state[key_grid]["✓"] == True].copy()

# ────────────────────────── PDF generation ─────────────────────
st.markdown("### 📄 Download PDF report")

if chosen.empty:
    st.caption("Select one or more mounts above to enable the PDF export.")
else:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(letter),
        topMargin=36,
        bottomMargin=36,
        leftMargin=36,
        rightMargin=36,
    )

    styles = getSampleStyleSheet()
    elements = []

    title = f"Bruker Mounts — {day.strftime('%Y-%m-%d')}"
    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Spacer(1, 12))

    pdf_cols = [
        "mount_code","mount_time","selection_label","cross_run_code",
        "clutch_name","clutch_nickname","annotations",
        "n_top","n_bottom","orientation","created_by"
    ]
    present_pdf = [c for c in pdf_cols if c in chosen.columns]
    data = [present_pdf] + chosen[present_pdf].astype(str).values.tolist()

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.25, colors.black),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
    ]))
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