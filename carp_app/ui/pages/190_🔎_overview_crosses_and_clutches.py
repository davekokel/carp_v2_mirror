# =============================================================================
# 🔎 Cross & Clutch Instances (direct joins; crosses + clutch_instances + v_tank_pairs)
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
import typing as t

import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.lib.db import get_engine
from carp_app.ui.lib.labels_components import download_button_for_labels

# ── Auth + page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🔎 Cross & Clutch Instances", page_icon="🧪", layout="wide")
st.title("🔎 Cross & Clutch Instances")

if not os.getenv("DB_URL"):
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

with eng.begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([2,1,1,1])
    q   = c1.text_input("Search (TP/FP/mom/dad/cross/clutch/genotype)")
    d1  = c2.date_input("From", value=None)
    d2  = c3.date_input("To",   value=None)
    lim = int(c4.number_input("Limit", min_value=10, max_value=2000, value=200, step=50))
    st.form_submit_button("Apply")

where_parts: list[str] = []
params: dict[str, t.Any] = {"lim": lim}

if q:
    params["q"] = f"%{q.strip()}%"
    where_parts.append("""(
      cr.tank_pair_code ilike :q or coalesce(vtp.fish_pair_code,'') ilike :q or
      coalesce(vtp.mom_fish_code,'') ilike :q or coalesce(vtp.dad_fish_code,'') ilike :q or
      coalesce(vtp.mom_tank_code,'') ilike :q or coalesce(vtp.dad_tank_code,'') ilike :q or
      coalesce(vtp.mom_genotype,'') ilike :q or coalesce(vtp.dad_genotype,'') ilike :q or
      coalesce(cl.clutch_genotype_pretty,'') ilike :q or
      coalesce(cr.cross_run_code,'') ilike :q or
      coalesce(cl.clutch_instance_code,'') ilike :q
    )""")

if d1:
    params["d1"] = str(d1)
    where_parts.append("(cr.cross_date >= :d1)")
if d2:
    params["d2"] = str(d2)
    where_parts.append("(cr.cross_date <= :d2)")

WHERE_SQL = (" where " + " and ".join(where_parts)) if where_parts else ""

# ── Query (direct joins: crosses + clutch_instances + v_tank_pairs) ──────────
sql = text(f"""
  with base as (
    select
      cr.id                         as cross_id,
      cr.cross_run_code             as cross_code,
      cr.tank_pair_code             as tank_pair_code,
      vtp.fish_pair_code            as fish_pair_code,
      vtp.mom_fish_code             as mom_fish_code,
      vtp.dad_fish_code             as dad_fish_code,
      vtp.mom_tank_code             as mom_tank_code,
      vtp.dad_tank_code             as dad_tank_code,
      coalesce(vtp.mom_genotype,'') as mom_genotype,
      coalesce(vtp.dad_genotype,'') as dad_genotype,
      cl.clutch_genotype_pretty     as clutch_genotype,
      cr.cross_date                 as cross_date,
      cr.created_at                 as cross_created_at,
      cl.id                         as clutch_instance_id,
      cl.clutch_instance_code       as clutch_code,
      cl.created_at                 as clutch_created_at
    from public.crosses cr
    left join public.clutch_instances cl
      on cl.cross_instance_id = cr.id
    left join public.v_tank_pairs vtp
      on vtp.tank_pair_code = cr.tank_pair_code
  )
  select *
  from base
  {WHERE_SQL}
  order by
    cross_date desc nulls last,
    coalesce(clutch_created_at, cross_created_at) desc nulls last
  limit :lim
""")

with eng.begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} instance(s)")
if df.empty:
    st.info("No instances yet."); st.stop()

# ── Display + Selection ──────────────────────────────────────────────────────
# ── Display + Selection ──────────────────────────────────────────────────────
sel_col = "✓ Select"
grid = df.copy()
if sel_col not in grid.columns:
    grid.insert(0, sel_col, False)

# Put these first, then the rest
first_cols = ["clutch_code", "clutch_genotype", "cross_date", "cross_code"]
ordered = [c for c in first_cols if c in grid.columns]
rest = [c for c in grid.columns if c not in ordered and c != sel_col]
display_cols = [sel_col] + ordered + rest

edited = st.data_editor(
    grid[display_cols],
    hide_index=True,
    width="stretch",
    column_config={
        sel_col:              st.column_config.CheckboxColumn("✓", default=False),

        # first four (now pinned left after the checkbox)
        "clutch_code":        st.column_config.TextColumn("Clutch code", disabled=True),
        "clutch_genotype":    st.column_config.TextColumn("Clutch genotype", disabled=True, width="large"),
        "cross_date":         st.column_config.DateColumn("Cross date", disabled=True, format="YYYY-MM-DD"),
        "cross_code":         st.column_config.TextColumn("Cross code", disabled=True),

        # keep the rest readable
        "tank_pair_code":     st.column_config.TextColumn("TP code", disabled=True),
        "fish_pair_code":     st.column_config.TextColumn("FP code", disabled=True),
        "mom_fish_code":      st.column_config.TextColumn("Mom FSH", disabled=True),
        "dad_fish_code":      st.column_config.TextColumn("Dad FSH", disabled=True),
        "mom_tank_code":      st.column_config.TextColumn("Mom tank", disabled=True),
        "dad_tank_code":      st.column_config.TextColumn("Dad tank", disabled=True),
        "mom_genotype":       st.column_config.TextColumn("Mom genotype", disabled=True, width="large"),
        "dad_genotype":       st.column_config.TextColumn("Dad genotype", disabled=True, width="large"),
        "clutch_created_at":  st.column_config.DatetimeColumn("Clutch created", disabled=True),
        "cross_created_at":   st.column_config.DatetimeColumn("Cross created", disabled=True),
      },
    key="cross_clutch_instances_editor",
)

mask = edited.get(sel_col, pd.Series(False, index=edited.index)).fillna(False).astype(bool)
picked = edited[mask]
if picked.empty:
    st.info("Select one or more rows to print labels.")
    st.stop()

# ── Label rows ───────────────────────────────────────────────────────────────
def _rows_for_cross_labels(df_sel: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for r in df_sel.to_dict(orient="records"):
        rows.append({
            "cross_code": r.get("cross_code"),
            "cross_date": r.get("cross_date"),
            "mother_tank_code": r.get("mom_tank_code"),
            "father_tank_code": r.get("dad_tank_code"),
            "mom_genotype": r.get("mom_genotype"),
            "dad_genotype": r.get("dad_genotype"),
            "clutch_instance_code": r.get("clutch_code") or "",
            "clutch_name": "",
        })
    return rows

def _rows_for_petri_labels(df_sel: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for r in df_sel.to_dict(orient="records"):
        cd = r.get("cross_date")
        dob = (cd + timedelta(days=1)) if isinstance(cd, (pd.Timestamp, date)) else None
        rows.append({
            "clutch_instance_code": r.get("clutch_code") or "",
            "clutch_name": "",
            "mom_code": r.get("mom_fish_code"),
            "dad_code": r.get("dad_fish_code"),
            "clutch_genotype": r.get("clutch_genotype") or "",
            "date_birth": dob,
        })
    return rows

have_parents = all(c in df.columns for c in ["mom_tank_code","dad_tank_code"])

st.subheader("Print labels")
c1, c2 = st.columns(2)
with c1:
    if have_parents:
        download_button_for_labels(
            rows=_rows_for_cross_labels(picked),
            builder="crossing",
            file_prefix="cross_labels",
            button_text="⬇️ Download CROSS labels (PDF)",
        )
    else:
        st.button("⬇️ Download CROSS labels (PDF)", disabled=True)
        st.caption("Need mom/dad tank codes in the view to print cross labels.")
with c2:
    download_button_for_labels(
        rows=_rows_for_petri_labels(picked),
        builder="petri",
        file_prefix="clutch_labels",
        button_text="⬇️ Download CLUTCH labels (PDF)",
    )

st.caption("Source: crosses + clutch_instances + v_tank_pairs • Petri DOB = cross_date + 1 day")