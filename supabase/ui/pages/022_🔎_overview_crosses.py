from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Optional, Tuple, List
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ---------- path + page ----------
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Overview — Crosses", page_icon="🔎", layout="wide")
st.title("🔎 Overview — Crosses")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL is not set"); st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

# ---------- helpers ----------
def exists(obj: str) -> bool:
    sch, tab = obj.split(".", 1)
    q = text("""
      select exists(
        select 1 from information_schema.tables where table_schema=:s and table_name=:t
        union all
        select 1 from information_schema.views  where table_schema=:s and table_name=:t
      ) as ok
    """)
    with eng.begin() as cx:
        return bool(pd.read_sql(q, cx, params={"s": sch, "t": tab})["ok"].iloc[0])

def pick_concept_source() -> Tuple[str, str]:
    """
    Pick a concept source that exists and return (name, sql)
    The SQL will select the columns we want for the grid.
    """
    CANDS = [
        ("public.vw_planned_clutches_overview_human",
         """select clutch_code, name, nickname, mom_code, dad_code, n_treatments, created_by, created_at
            from public.vw_planned_clutches_overview_human"""),
        ("public.vw_planned_clutches_overview",
         """select clutch_code, name, nickname, mom_code, dad_code, n_treatments, created_by, created_at
            from public.vw_planned_clutches_overview"""),
        ("public.planned_crosses",
         """select clutch_code, coalesce(name,'') as name, coalesce(nickname,'') as nickname,
                   mom_code, dad_code, coalesce(n_treatments,0) as n_treatments,
                   coalesce(created_by,'') as created_by, created_at
            from public.planned_crosses"""),
    ]
    for name, sql in CANDS:
        if exists(name):
            return name, sql
    return "", ""

def pick_instances_source() -> Optional[Tuple[str, str]]:
    """
    Pick an instance source that has a recognizable clutch code column.
    Return (name, code_col) or None.
    """
    CANDS = [
        "public.vw_cross_runs_overview",
        "public.v_cross_plan_runs_enriched",
        "public.v_crosses_status",
        "public.cross_instances",
    ]
    CODE_CAND_COLS = ["clutch_code", "planned_clutch_code", "clutch", "clutch_id", "concept_code"]
    qcols = text("""
      select column_name from information_schema.columns
      where table_schema=:s and table_name=:t
    """)
    for full in CANDS:
        if not exists(full):
            continue
        sch, tab = full.split(".", 1)
        with eng.begin() as cx:
            cols = pd.read_sql(qcols, cx, params={"s": sch, "t": tab})["column_name"].tolist()
        for col in CODE_CAND_COLS:
            if col in cols:
                return full, col
    return None

SRC_NAME, SRC_SQL = pick_concept_source()
if not SRC_NAME:
    st.info("No concept source found (expected one of vw_planned_clutches_overview_human / vw_planned_clutches_overview / planned_crosses).")
    st.stop()

inst_src = pick_instances_source()  # may be None; we handle gracefully

# ---------- filters ----------
with st.form("filters"):
    c1, c2, c3 = st.columns([3,1,1])
    q = c1.text_input("Search planned clutches (code/name/nickname/mom/dad)")
    limit = int(c2.number_input("Limit", min_value=10, max_value=5000, value=200, step=50))
    who = c3.text_input("Created by", value="")
    submitted = st.form_submit_button("Apply")

# ---------- load concepts ----------
base_sql = f"select * from ({SRC_SQL}) x"
where = []
params = {}
if q:
    ql = f"%{q.strip()}%"
    where.append("(clutch_code ilike :q or name ilike :q or nickname ilike :q or mom_code ilike :q or dad_code ilike :q)")
    params["q"] = ql
if who.strip():
    where.append("created_by = :u")
    params["u"] = who.strip()

where_sql = (" where " + " and ".join(where)) if where else ""
sql = text(f"""
  {base_sql}
  {where_sql}
  order by created_at desc nulls last
  limit :lim
""")
params["lim"] = limit
with eng.begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} planned clutch(es)")
if df.empty:
    st.info("No planned clutches match."); st.stop()

# ---------- selection model ----------
if "_cross_concepts" not in st.session_state:
    t = df.copy()
    t.insert(0, "✓ Select", False)
    st.session_state["_cross_concepts"] = t

# keep session model updated for current filter result (align rows by clutch_code)
sess = st.session_state["_cross_concepts"].set_index("clutch_code")
now  = df.set_index("clutch_code")
# add any new rows
missing_idx = [i for i in now.index if i not in sess.index]
if missing_idx:
    sess = pd.concat([sess, now.loc[missing_idx]], axis=0)
# drop rows not in current filter
sess = sess.loc[now.index]
st.session_state["_cross_concepts"] = sess.reset_index()

# bulk controls
b1, b2 = st.columns([1,1])
with b1:
    if st.button("Select all"):
        st.session_state["_cross_concepts"]["✓ Select"] = True
with b2:
    if st.button("Clear all"):
        st.session_state["_cross_concepts"]["✓ Select"] = False

# show concepts grid
view_cols = ["✓ Select","clutch_code","name","nickname","mom_code","dad_code","n_treatments","created_by","created_at"]
view_cols = [c for c in view_cols if c in st.session_state["_cross_concepts"].columns]
st.dataframe(st.session_state["_cross_concepts"][view_cols], use_container_width=True, hide_index=True)

# ---------- instances for each selected concept ----------
sel_codes = st.session_state["_cross_concepts"].loc[
    st.session_state["_cross_concepts"]["✓ Select"] == True, "clutch_code"
].astype(str).tolist()

if not sel_codes:
    st.info("Select at least one planned clutch to show existing cross instances.")
    st.stop()

st.divider()
st.subheader("Existing cross instances for selected concept(s)")

if not inst_src:
    st.info("No instance view/table found (expected one of vw_cross_runs_overview / v_cross_plan_runs_enriched / v_crosses_status / cross_instances).")
else:
    src_name, code_col = inst_src
    qcols = text("""
      select column_name from information_schema.columns
      where table_schema=:s and table_name=:t
    """)
    sch, tab = src_name.split(".", 1)
    with eng.begin() as cx:
        inst_cols = pd.read_sql(qcols, cx, params={"s": sch, "t": tab})["column_name"].tolist()

    def _fetch(code: str) -> pd.DataFrame:
        with eng.begin() as cx:
            return pd.read_sql(text(f"""
                select *
                from {src_name}
                where {code_col} = :code
                order by
                  coalesce(nullif(to_char(coalesce(created_at, run_date, date, updated_at), 'YYYY-MM-DD HH24:MI:SS'), ''), '9999-12-31 23:59:59') desc
                limit 500
            """), cx, params={"code": code})

    for code in sel_codes:
        st.markdown(f"**{code}**")
        try:
            df_i = _fetch(code)
        except Exception as e:
            st.warning(f"Failed to load instances for {code}: {e}")
            continue
        if df_i.empty:
            st.caption("No instances.")
            continue
        st.dataframe(df_i, use_container_width=True, hide_index=True)
        st.markdown("---")
