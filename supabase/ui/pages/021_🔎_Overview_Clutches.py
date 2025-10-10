from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    try:
        from auth_gate import require_app_unlock
    except Exception:
        def require_app_unlock(): ...
require_app_unlock()

import os
from datetime import date, timedelta
from typing import List

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PAGE_TITLE = "CARP — Clutches (Concept → Instances)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🔎", layout="wide")
st.title("🔎 Clutches — Conceptual overview with instance counts")

def _ensure_sslmode(url: str) -> str:
    from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
    u = urlparse(url); q = dict(parse_qsl(u.query, keep_blank_values=True))
    host = (u.hostname or "").lower() if u.hostname else ""
    q["sslmode"] = "disable" if host in {"localhost","127.0.0.1","::1"} else q.get("sslmode","require")
    return urlunparse((u.scheme,u.netloc,u.path,u.params,urlencode(q),u.fragment))

@st.cache_resource(show_spinner=False)
def _get_engine():
    url = os.environ.get("DB_URL")
    if not url: st.stop()
    return create_engine(_ensure_sslmode(url))

ENGINE = _get_engine()

def load_concept_overview() -> pd.DataFrame:
    with ENGINE.connect() as cx:
        df = pd.read_sql(
            text("""
                select
                  clutch_plan_id,
                  planned_cross_id,
                  clutch_code,
                  clutch_name,
                  clutch_nickname,
                  date_planned,
                  created_by,
                  created_at,
                  note,
                  n_instances,
                  n_containers,
                  n_crosses,
                  latest_date_birth
                from public.vw_clutches_concept_overview
                order by coalesce(date_planned::timestamp, created_at) desc nulls last
            """),
            cx,
        )
    return df

def load_instances_for_plans(plan_ids: List[str]) -> pd.DataFrame:
    if not plan_ids:
        return pd.DataFrame()
    with ENGINE.connect() as cx:
        df = pd.read_sql(
            text("""
                select
                  c.id_uuid::text             as clutch_id,
                  c.planned_cross_id::text    as planned_cross_id,
                  c.date_birth,
                  c.created_by,
                  c.created_at,
                  c.note,
                  (select count(*) from public.clutch_containers cc where cc.clutch_id = c.id_uuid)::int as n_containers,
                  case when c.cross_id is null then 0 else 1 end::int as has_cross
                from public.clutches c
                where c.planned_cross_id::text = any(:ids)
                order by coalesce(c.date_birth::timestamp, c.created_at) desc nulls last
            """),
            cx,
            params={"ids": plan_ids},
        )
    return df

with st.sidebar:
    st.header("Filters")
    q = st.text_input("Search (code / name / user / note)")
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("From", value=date.today() - timedelta(days=60))
    with col2:
        end = st.date_input("To", value=date.today())

base = load_concept_overview()

if q:
    ql = q.lower()
    def contains(s: pd.Series) -> pd.Series:
        return s.astype(str).str.lower().str.contains(ql, na=False)
    mask = (
        contains(base.get("clutch_code", pd.Series(index=base.index))) |
        contains(base.get("clutch_name", pd.Series(index=base.index))) |
        contains(base.get("created_by", pd.Series(index=base.index))) |
        contains(base.get("note", pd.Series(index=base.index)))
    )
    base = base[mask]

if "date_planned" in base.columns:
    dp = pd.to_datetime(base["date_planned"], errors="coerce")
    base = base[dp.isna() | dp.between(pd.to_datetime(start), pd.to_datetime(end), inclusive="both")]

st.subheader("Conceptual clutches")
if base.empty:
    st.info("No rows for the current filters.")
    st.stop()

view_cols = [c for c in [
    "clutch_code","clutch_name","clutch_nickname",
    "date_planned","created_by","created_at","note",
    "n_instances","n_containers","n_crosses","latest_date_birth",
] if c in base.columns]

df_view = base[view_cols + (["clutch_plan_id"] if "clutch_plan_id" in base.columns else [])].copy()
if "clutch_plan_id" in df_view.columns:
    df_view = df_view.set_index("clutch_plan_id", drop=True).drop(columns=["clutch_plan_id"], errors="ignore")
df_view.index = df_view.index.map(str)
df_view.insert(0, "✅", False)

edited = st.data_editor(
    df_view,
    hide_index=True,
    use_container_width=True,
    column_config={
        "✅": st.column_config.CheckboxColumn(help="Select clutches to see realized instances"),
        "clutch_name": st.column_config.TextColumn(width="large"),
        "clutch_code": st.column_config.TextColumn(width="medium"),
        "date_planned": st.column_config.DateColumn(format="YYYY-MM-DD", width="small"),
        "latest_date_birth": st.column_config.DateColumn(format="YYYY-MM-DD", width="small"),
        "n_instances": st.column_config.NumberColumn(width="small"),
        "n_containers": st.column_config.NumberColumn(width="small"),
        "n_crosses": st.column_config.NumberColumn(width="small"),
    },
    key="clutches_concept_editor",
)

selected_plan_ids = edited.index[edited["✅"] == True].tolist()

st.divider()
st.subheader("Realized instances for selection")
if not selected_plan_ids:
    st.caption("Select one or more conceptual clutches above to list realized clutch instances.")
else:
    inst = load_instances_for_plans(selected_plan_ids)
    if inst.empty:
        st.info("No realized clutch instances yet.")
    else:
        st.dataframe(
            inst.rename(columns={
                "clutch_id":"clutch_id",
                "planned_cross_id":"planned_cross_id",
                "date_birth":"date_birth",
                "created_by":"created_by",
                "created_at":"created_at",
                "note":"note",
                "n_containers":"n_containers",
                "has_cross":"has_cross",
            }),
            use_container_width=True,
            hide_index=True,
        )