from __future__ import annotations

import os
from pathlib import Path
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import sys 

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

# ────────────────────────── pull mounts for the day with enrichment ─────────────
with eng.begin() as cx:
    df = pd.read_sql(
        text("""
          select
            mount_code, mount_date, mount_time,
            selection_label, cross_run_code,
            clutch_name, clutch_nickname, annotations_rollup,
            n_top, n_bottom, orientation,
            created_at, created_by
          from public.v_bruker_mounts_enriched
          where mount_date = :d
          order by created_at desc
        """),
        cx,
        params={"d": day},
    )
    df = pd.read_sql(sql, cx, params={"d": day})

if df.empty:
    _banner_warn("No mounts found for the selected day.")
    st.stop()

# ────────────────────────── grid + selection ───────────────────
st.markdown("### Mounts on selected day")

# ensure column order includes the three new fields prominently
cols_order = [
    "mount_code",
    "mount_date",
    "mount_time",
    "selection_label",
    "cross_run_code",
    "clutch_name",           # NEW
    "clutch_nickname",       # NEW
    "annotations_rollup",    # NEW
    "n_top",
    "n_bottom",
    "orientation",
    "created_at",
    "created_by",
]
present = [c for c in cols_order if c in df.columns]
# add any remaining columns to the tail
present += [c for c in df.columns if c not in present]
df = df[present].copy()

# Add a checkbox column for selection
key_grid = "_overview_mounts_grid"
if key_grid not in st.session_state:
    t = df.copy()
    t.insert(0, "✓", False)
    st.session_state[key_grid] = t
else:
    base = st.session_state[key_grid]
    # try to align by mount_code + timestamp to stay stable
    if "mount_code" in df.columns and "created_at" in df.columns:
        base = base.set_index(["mount_code","created_at"])
        now  = df.set_index(["mount_code","created_at"])
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
    column_order=["✓"] + present,
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False)},
    key="overview_mounts_editor",
)
st.session_state[key_grid].loc[grid_edit.index, "✓"] = grid_edit["✓"]

left, right = st.columns([1,1])
with left:
    if st.button("Select all"):
        st.session_state[key_grid]["✓"] = True
        st.experimental_rerun()
with right:
    if st.button("Clear"):
        st.session_state[key_grid]["✓"] = False
        st.experimental_rerun()

# Selected rows for PDF
chosen = st.session_state[key_grid].loc[st.session_state[key_grid]["✓"] == True].copy()

# ────────────────────────── PDF report (very simple stub) ──────────
st.markdown("### Print PDF report")
if chosen.empty:
    st.caption("Select one or more mounts above to enable the PDF export.")
else:
    # Tiny HTML summary – your existing PDF generator can consume this
    html = """
    <h2>Bruker Mounts – {day}</h2>
    <table border="1" cellspacing="0" cellpadding="4">
      <thead>
        <tr>
          <th>mount_code</th>
          <th>time</th>
          <th>selection</th>
          <th>cross_run</th>
          <th>clutch</th>
          <th>nickname</th>
          <th>annotations</th>
          <th>n_top</th>
          <th>n_bottom</th>
          <th>orientation</th>
        </tr>
      </thead>
      <tbody>
    """.format(day=day.isoformat())

    for _, r in chosen.iterrows():
        html += f"""
          <tr>
            <td>{r.get('mount_code','')}</td>
            <td>{r.get('mount_time','')}</td>
            <td>{r.get('selection_label','')}</td>
            <td>{r.get('cross_run_code','')}</td>
            <td>{r.get('clutch_name','')}</td>
            <td>{r.get('clutch_nickname','')}</td>
            <td>{r.get('annotations_rollup','')}</td>
            <td>{r.get('n_top','')}</td>
            <td>{r.get('n_bottom','')}</td>
            <td>{r.get('orientation','')}</td>
          </tr>
        """

    html += """
      </tbody>
    </table>
    """

    # For now, let the user download the HTML. Your PDF pipeline can convert it downstream.
    st.download_button(
        "⬇️ Download report (HTML)",
        data=html.encode("utf-8"),
        file_name=f"bruker_mounts_{day.isoformat()}.html",
        mime="text/html",
        use_container_width=True,
    )