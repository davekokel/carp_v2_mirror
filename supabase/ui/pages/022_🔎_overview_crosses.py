from __future__ import annotations
import os, sys
from pathlib import Path
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ----- path bootstrap -----
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Overview — Crosses", page_icon="🔎", layout="wide")
st.title("🔎 Overview — Crosses")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

# ---------- helpers ----------
def _exists(full: str) -> bool:
    sch, tab = full.split(".", 1)
    q = text("""
      select exists(
        select 1 from information_schema.tables where table_schema=:s and table_name=:t
        union all
        select 1 from information_schema.views  where table_schema=:s and table_name=:t
      ) as ok
    """)
    with eng.begin() as cx:
        return bool(pd.read_sql(q, cx, params={"s": sch, "t": tab})["ok"].iloc[0])

def _pick_instances_source() -> tuple[str, str] | None:
    """
    Return (source_name, code_col) for instances view/table.
    """
    cands = [
        "public.vw_cross_runs_overview",
        "public.v_cross_plan_runs_enriched",
        "public.v_crosses_status",
        "public.cross_instances",
    ]
    code_cols = ["clutch_code", "planned_clutch_code", "clutch", "clutch_id", "concept_code"]
    qcols = text("""
      select column_name from information_schema.columns
      where table_schema=:s and table_name=:t
    """)
    for full in cands:
        if not _exists(full): 
            continue
        sch, tab = full.split(".", 1)
        with eng.begin() as cx:
            cols = pd.read_sql(qcols, cx, params={"s": sch, "t": tab})["column_name"].tolist()
        for c in code_cols:
            if c in cols:
                return full, c
    return None

# ---------- concept source (exact to your staging schema) ----------
if not _exists("public.vw_planned_clutches_overview"):
    st.info("Expected view public.vw_planned_clutches_overview not found.")
    st.stop()

# Build the projection you want:
# clutch_code, name (clutch_name), nickname (clutch_nickname), mom_code, dad_code, n_treatments, created_by, created_at
PROJ_SQL = """
  select
    v.clutch_code::text                               as clutch_code,
    coalesce(v.clutch_name,'')::text                  as name,
    coalesce(v.clutch_nickname,'')::text              as nickname,
    coalesce(pc.mom_code,'')::text                    as mom_code,
    coalesce(pc.dad_code,'')::text                    as dad_code,
    coalesce(v.n_treatments,0)::int                   as n_treatments,
    coalesce(v.created_by,'')::text                   as created_by,
    v.created_at::timestamptz                         as created_at
  from public.vw_planned_clutches_overview v
  left join public.planned_crosses pc
    on pc.cross_code = v.clutch_code
"""

# ---------- filters ----------
with st.form("filters"):
    c1, c2, c3 = st.columns([3, 1, 1])
    q  = c1.text_input("Search (code/name/nickname/mom/dad)")
    d1 = c2.date_input("From", value=None)
    d2 = c3.date_input("To", value=None)
    submitted = st.form_submit_button("Apply")

where = []
params: dict[str, object] = {}
if q:
    params["q"] = f"%{q.strip()}%"
    where.append("(clutch_code ilike :q or name ilike :q or nickname ilike :q or mom_code ilike :q or dad_code ilike :q)")
if d1:
    where.append("created_at >= :d1"); params["d1"] = str(d1)
if d2:
    where.append("created_at <= :d2"); params["d2"] = str(d2)

where_sql = (" where " + " and ".join(where)) if where else ""

# ---------- load concepts ----------
sql = text(f"""
  select * from (
    {PROJ_SQL}
  ) x
  {where_sql}
  order by created_at desc nulls last
  limit 500
""")
with eng.begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

# Debug chip: show which sources we used
inst_src = _pick_instances_source()
st.caption(f"concepts: vw_planned_clutches_overview  |  instances: {inst_src[0]} ({inst_src[1]})" if inst_src else "concepts: vw_planned_clutches_overview  |  instances: none")

st.caption(f"{len(df)} planned clutch(es)")
if df.empty:
    st.info("No planned clutches match."); st.stop()

# ---------- session editor with checkbox ----------
key = "_cross_concepts"
if key not in st.session_state:
    t = df.copy()
    t.insert(0, "✓ Select", False)
    st.session_state[key] = t

# keep session aligned on clutch_code
base = st.session_state[key].set_index("clutch_code")
now  = df.set_index("clutch_code")
for i in now.index:
    if i not in base.index: base.loc[i] = now.loc[i]
base = base.loc[now.index]  # drop rows not in current filter
st.session_state[key] = base.reset_index()

view_cols = ["✓ Select","clutch_code","name","nickname","mom_code","dad_code","n_treatments","created_by","created_at"]
edited = st.data_editor(
    st.session_state[key][view_cols],
    hide_index=True, use_container_width=True,
    column_config={
        "✓ Select":      st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code":   st.column_config.TextColumn("clutch_code", disabled=True),
        "name":          st.column_config.TextColumn("name", disabled=True),
        "nickname":      st.column_config.TextColumn("nickname", disabled=True),
        "mom_code":      st.column_config.TextColumn("mom_code", disabled=True),
        "dad_code":      st.column_config.TextColumn("dad_code", disabled=True),
        "n_treatments":  st.column_config.NumberColumn("n_treatments", disabled=True),
        "created_by":    st.column_config.TextColumn("created_by", disabled=True),
        "created_at":    st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key="crosses_editor",
)
# persist checkbox back to session
st.session_state[key].loc[edited.index, "✓ Select"] = edited["✓ Select"]

sel_codes = edited.loc[edited["✓ Select"]==True, "clutch_code"].astype(str).tolist()
if not sel_codes:
    st.info("Select one or more planned clutches to show existing instances.")
    st.stop()

st.divider()
st.subheader("Existing cross instances")

if not inst_src:
    st.info("No instance view/table found (vw_cross_runs_overview / v_cross_plan_runs_enriched / v_crosses_status / cross_instances).")
else:
    src_name, code_col = inst_src
    for code in sel_codes:
        st.markdown(f"**{code}**")
        try:
            with eng.begin() as cx:
                df_i = pd.read_sql(
                    text(f"select * from {src_name} where {code_col} = :code order by 1 desc"),
                    cx, params={"code": code}
                )
        except Exception as e:
            st.warning(f"Failed for {code}: {e}")
            continue
        if df_i.empty:
            st.caption("No instances.")
            continue
        st.dataframe(df_i, use_container_width=True, hide_index=True)
        st.markdown("---")