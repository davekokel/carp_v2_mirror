from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()
from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Overview Clutches", page_icon="🧬", layout="wide")
st.title("🧬 Clutches — Conceptual overview with instance counts")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

# ───────────────────────── helpers ─────────────────────────
def _annotations_for_clutches(selected_codes: List[str], limit: int = 100) -> pd.DataFrame:
    if not selected_codes:
        return pd.DataFrame()

    sql = """
      select
        cp.clutch_code,
        ci.clutch_instance_code,
        cinst.clutch_birthday as birthday,
        ci.red_intensity,
        ci.green_intensity,
        ci.notes,
        ci.annotated_by,
        ci.annotated_at
      from public.clutch_plans cp
      join public.planned_crosses pc   on pc.clutch_id = cp.id
      join public.crosses x            on x.id = pc.cross_id
      join public.cross_instances cinst on cinst.cross_id = x.id
      join public.clutch_instances ci  on ci.cross_instance_id = cinst.id
      where cp.clutch_code = any(%(codes)s::text[])
      order by coalesce(ci.annotated_at, ci.created_at) desc,
               ci.created_at desc
      limit %(lim)s
    """
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": selected_codes, "lim": int(limit)})
    
def _exists(schema_dot_name: str) -> bool:
    sch, tab = schema_dot_name.split(".", 1)
    q = text("""
      with t as (
        select table_schema as s, table_name as t from information_schema.tables
        union all
        select table_schema as s, table_name as t from information_schema.views
      )
      select exists(select 1 from t where s=:s and t=:t) as ok
    """)
    with eng.begin() as cx:
        return bool(pd.read_sql(q, cx, params={"s": sch, "t": tab})["ok"].iloc[0])

def _load_concepts() -> pd.DataFrame:
    if not _exists("public.v_clutches"):
        st.error("Missing view public.v_clutches."); st.stop()
    with eng.begin() as cx:
        return pd.read_sql(
            """
            select
              conceptual_cross_code as clutch_code,
              name                  as clutch_name,
              nickname              as clutch_nickname,
              mom_code, dad_code, mom_code_tank, dad_code_tank,
              created_at
            from public.v_clutches
            order by created_at desc nulls last, conceptual_cross_code
            limit 2000
            """,
            cx,
        )

def _load_counts() -> pd.DataFrame:
    if not _exists("public.v_clutch_counts"):
        # Soft fallback if migration not applied yet
        return pd.DataFrame(columns=[
            "clutch_code","runs_count","annotations_count","last_birthday","last_annotated_at"
        ])
    with eng.begin() as cx:
        return pd.read_sql(
            """
            select clutch_code, runs_count, annotations_count, last_birthday, last_annotated_at
            from public.v_clutch_counts
            """,
            cx,
        )

def _runs_preview(selected_codes: List[str], limit: int = 50) -> pd.DataFrame:
    if not selected_codes:
        return pd.DataFrame()
    sql = """
      select
        cp.clutch_code,
        ci.cross_run_code,
        ci.clutch_birthday as birthday,
        ci.cross_date,
        x.mother_code as mom_code,
        x.father_code as dad_code
      from public.clutch_plans cp
      join public.planned_crosses pc on pc.clutch_id = cp.id
      join public.crosses x          on x.id = pc.cross_id
      join public.cross_instances ci  on ci.cross_id = x.id
      where cp.clutch_code = any(%(codes)s::text[])
      order by ci.clutch_birthday desc, ci.cross_date desc, ci.created_at desc nulls last
      limit %(lim)s
    """
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": selected_codes, "lim": int(limit)})

# ───────────────────────── load & merge ─────────────────────────
concepts = _load_concepts()
counts   = _load_counts()
df = concepts.merge(counts, on="clutch_code", how="left")

for c, default in [("runs_count", 0), ("annotations_count", 0)]:
    if c not in df.columns:
        df[c] = default

st.caption("DB: " + (getattr(getattr(eng, "url", None), "host", None) or os.getenv("PGHOST", "(unknown)"))
           + " • instances via planned_crosses → cross_instances")

# ───────────────────────── session table with selection ─────────────────────────
key = "_overview_clutches_table"
def _sessionize(base: pd.DataFrame) -> pd.DataFrame:
    t = base.copy()
    if "✓ Select" not in t.columns:
        t.insert(0, "✓ Select", False)
    else:
        cols = t.columns.tolist()
        cols.remove("✓ Select")
        t = t[["✓ Select"] + cols]
    return t

if key not in st.session_state:
    st.session_state[key] = _sessionize(df)
else:
    # re-align but keep checkboxes when rows persist
    current = st.session_state[key].set_index("clutch_code")
    now     = _sessionize(df).set_index("clutch_code")
    for code in now.index:
        if code not in current.index:
            current.loc[code] = now.loc[code]
        else:
            for col in now.columns:
                if col != "✓ Select":
                    current.at[code, col] = now.at[code, col]
    current = current.loc[now.index]
    st.session_state[key] = current.reset_index()

# ───────────────────────── filters (lightweight search) ─────────────────────────
with st.form("filters"):
    c1, c2 = st.columns([3, 1])
    q  = c1.text_input("Search (clutch/code/nickname/mom/dad)")
    lim = int(c2.number_input("Limit", min_value=10, max_value=2000, value=200, step=10))
    _ = st.form_submit_button("Apply")

table = st.session_state[key]
if q:
    ql = q.strip().lower()
    def _contains(s: pd.Series) -> pd.Series:
        return s.fillna("").astype(str).str.lower().str.contains(ql)
    mask = (
        _contains(table["clutch_code"]) |
        _contains(table.get("clutch_name", pd.Series())) |
        _contains(table.get("clutch_nickname", pd.Series())) |
        _contains(table.get("mom_code", pd.Series())) |
        _contains(table.get("dad_code", pd.Series()))
    )
    table = table[mask]

table = table.head(lim)

# ───────────────────────── conceptual grid with counts ─────────────────────────
cols_order = [
    "✓ Select",
    "clutch_code","clutch_name","clutch_nickname",
    "mom_code","dad_code",
    "runs_count","annotations_count",
    "created_at",
]
present = [c for c in cols_order if c in table.columns]
edited = st.data_editor(
    table[present],
    hide_index=True,
    use_container_width=True,
    column_order=present,
    column_config={
        "✓ Select":           st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code":        st.column_config.TextColumn("Clutch", disabled=True),
        "clutch_name":        st.column_config.TextColumn("Cross name", disabled=True),
        "clutch_nickname":    st.column_config.TextColumn("Nickname", disabled=True),
        "mom_code":           st.column_config.TextColumn("Mom", disabled=True),
        "dad_code":           st.column_config.TextColumn("Dad", disabled=True),
        "runs_count":         st.column_config.NumberColumn("# runs", disabled=True, step=1, format="%d"),
        "annotations_count":  st.column_config.NumberColumn("# annotations", disabled=True, step=1, format="%d"),
        "created_at":         st.column_config.DatetimeColumn("Created", disabled=True),
    },
    key="clutches_editor",
)
# push back selection
st.session_state[key].loc[edited.index, "✓ Select"] = edited["✓ Select"]

# ───────────────────────── KPI band for current selection ─────────────────────────
sel_codes = edited.loc[edited.get("✓ Select", False) == True, "clutch_code"].astype(str).tolist()

if sel_codes:
    sub = df[df["clutch_code"].isin(sel_codes)]
    total_runs = int(sub["runs_count"].fillna(0).sum())
    total_ann  = int(sub["annotations_count"].fillna(0).sum())
    last_bday  = sub["last_birthday"].max() if "last_birthday" in sub.columns else None
    last_ann   = sub["last_annotated_at"].max() if "last_annotated_at" in sub.columns else None

    k1, k2, k3, k4 = st.columns([1,1,1,1])
    k1.metric("Runs (selected)", f"{total_runs}")
    k2.metric("Annotations (selected)", f"{total_ann}")
    k3.metric("Last birthday", f"{last_bday}" if pd.notna(last_bday) else "—")
    k4.metric("Last annotated", f"{last_ann}" if pd.notna(last_ann) else "—")

# ───────────────────────── optional: newest-first runs preview ─────────────────────────
st.markdown("### Annotations (selected clutches)")
if not sel_codes:
    st.info("Select clutches above to see recent annotations.")
else:
    ann = _annotations_for_clutches(sel_codes, limit=200)
    if ann.empty:
        st.caption("No annotations yet for the selected clutch(es).")
    else:
        # Clutch-focused fields only; no cross_* columns
        cols = [
            "clutch_code",
            "clutch_instance_code",
            "birthday",
            "red_intensity","green_intensity",
            "notes","annotated_by","annotated_at",
        ]
        present = [c for c in cols if c in ann.columns]
        st.dataframe(ann[present], hide_index=True, use_container_width=True)