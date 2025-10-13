from supabase.ui.email_otp_gate import require_email_otp
require_email_otp()

from __future__ import annotations
import os, sys
from pathlib import Path
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ───────────────────────── path bootstrap ─────────────────────────
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Overview — Crosses", page_icon="🔎", layout="wide")
st.title("🔎 Overview — Crosses")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

# ───────────────────────── helpers ─────────────────────────
def _exists(full: str) -> bool:
    """Does table/view exist."""
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
    Pick an instance source and its clutch-code column.
    Tries these in order and returns (source_name, code_column).
    """
    cands = [
        "public.vw_cross_runs_overview",
        "public.v_cross_plan_runs_enriched",
        "public.v_crosses_status",
        "public.cross_instances",
    ]
    code_cols = ["clutch_code", "planned_clutch_code", "clutch", "clutch_id", "concept_code"]
    qcols = text("""select column_name from information_schema.columns
                    where table_schema=:s and table_name=:t""")
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

# ───────────────────────── concepts source (stable view) ─────────────────────────
VIEW = "public.v_cross_concepts_overview"  # columns: conceptual_cross_code, clutch_code, name, nickname, mom_code, dad_code, mom_code_tank, dad_code_tank, n_treatments, created_by, created_at
if not _exists(VIEW):
    st.error(f"Expected view {VIEW} not found. Create it, then reload."); st.stop()

inst_src = _pick_instances_source()

# ───────────────────────── filters ─────────────────────────
with st.form("filters"):
    c1, c2, c3 = st.columns([3, 1, 1])
    q  = c1.text_input("Search (code/name/nickname/mom/dad)")
    d1 = c2.date_input("From", value=None)
    d2 = c3.date_input("To", value=None)
    _  = st.form_submit_button("Apply")

where, params = [], {}
if q:
    params["q"] = f"%{q.strip()}%"
    where.append(
        "(conceptual_cross_code ilike :q or clutch_code ilike :q or "
        " name ilike :q or nickname ilike :q or mom_code ilike :q or dad_code ilike :q or "
        " mom_code_tank ilike :q or dad_code_tank ilike :q)"
    )
if d1:
    where.append("created_at >= :d1"); params["d1"] = str(d1)
if d2:
    where.append("created_at <= :d2"); params["d2"] = str(d2)
runnable_only = st.toggle("Runnable only (both parents have live tanks)", value=False)
if runnable_only:
    where.append("(mom_code_tank <> '' and dad_code_tank <> '')")
where_sql = (" where " + " and ".join(where)) if where else ""

# ───────────────────────── load concepts ─────────────────────────
sql = text(f"""
  select *
  from {VIEW}
  {where_sql}
  order by created_at desc nulls last
  limit 500
""")
with eng.begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"concepts: {VIEW}  |  instances: {inst_src[0]} ({inst_src[1]})" if inst_src else f"concepts: {VIEW}  |  instances: none")
st.caption(f"{len(df)} planned clutch(es)")
if df.empty:
    st.info("No planned clutches match."); st.stop()

# ───────────────────────── session editor with checkbox ─────────────────────────
key = "_cross_concepts"
required = {
    "conceptual_cross_code","clutch_code","name","nickname",
    "mom_code","dad_code","mom_code_tank","dad_code_tank",
    "n_treatments","created_by","created_at"
}

def _new_session_table() -> pd.DataFrame:
    t = df.copy()
    if "✓ Select" not in t.columns:
        t.insert(0, "✓ Select", False)
    else:
        cols = t.columns.tolist()
        cols.remove("✓ Select")
        t = t[["✓ Select"] + cols]
    return t

if key not in st.session_state:
    st.session_state[key] = _new_session_table()
else:
    # reset if required columns not present (e.g., after view update)
    have = set(st.session_state[key].columns)
    if not required.issubset(have):
        st.session_state[key] = _new_session_table()

# keep session aligned on clutch_code
base = st.session_state[key].set_index("clutch_code", drop=False)
now  = df.set_index("clutch_code", drop=False)
for i in now.index:
    if i not in base.index:
        base.loc[i] = now.loc[i]
base = base.loc[now.index]  # drop filtered-out rows
st.session_state[key] = base.reset_index(drop=True)

# ───────────────────────── concept grid ─────────────────────────
# lock explicit order; conceptual_cross_code second
view_cols = [
    "✓ Select",
    "conceptual_cross_code",
    "clutch_code",
    "name","nickname",
    "mom_code","dad_code","mom_code_tank","dad_code_tank",
    "n_treatments","created_by","created_at",
]
cols_present = [c for c in view_cols if c in st.session_state[key].columns]

edited = st.data_editor(
    st.session_state[key][cols_present],
    hide_index=True,
    use_container_width=True,
    column_order=cols_present,
    column_config={
        "✓ Select":                st.column_config.CheckboxColumn(label="✓", default=False),
        "conceptual_cross_code":   st.column_config.TextColumn(label="conceptual_cross_code", disabled=True),
        "clutch_code":             st.column_config.TextColumn(label="cross", disabled=True),
        "name":                    st.column_config.TextColumn(label="cross name", disabled=True),
        "nickname":                st.column_config.TextColumn(label="nickname", disabled=True),
        "mom_code":                st.column_config.TextColumn(label="mom", disabled=True),
        "dad_code":                st.column_config.TextColumn(label="dad", disabled=True),
        "mom_code_tank":           st.column_config.TextColumn(label="mom tank", disabled=True),
        "dad_code_tank":           st.column_config.TextColumn(label="dad tank", disabled=True),
        "n_treatments":            st.column_config.NumberColumn(label="n_treatments", disabled=True),
        "created_by":              st.column_config.TextColumn(label="created_by", disabled=True),
        "created_at":              st.column_config.DatetimeColumn(label="created_at", disabled=True),
    },
    key="crosses_editor",
)
# persist checkbox back to session
if "✓ Select" in edited.columns:
    st.session_state[key].loc[edited.index, "✓ Select"] = edited["✓ Select"]

sel_codes = edited.loc[edited["✓ Select"] == True, "clutch_code"].astype(str).tolist()
if not sel_codes:
    st.info("Select one or more planned clutches to show existing instances.")
    st.stop()

# ───────────────────────── instances (per selected concept) ─────────────────────────
# ───────────────────────── instances (per selected concept) ─────────────────────────
st.divider()
st.subheader("Existing cross instances")

def _fetch_instances_for_concept(code: str) -> pd.DataFrame:
    """
    Resolve mom_code/dad_code for the concept, then fetch runs from
    vw_cross_runs_overview that match mom_code AND dad_code.
    """
    with eng.begin() as cx:
        m = pd.read_sql(
            text("""
                select mom_code, dad_code
                from public.v_cross_concepts_overview
                where conceptual_cross_code = :code
            """),
            cx, params={"code": code}
        )
        if m.empty:
            return pd.DataFrame()
        mom = (m["mom_code"].iloc[0] or "").strip()
        dad = (m["dad_code"].iloc[0] or "").strip()
        if not mom or not dad:
            return pd.DataFrame()

        q = text("""
          select
            r.cross_run_code,
            r.cross_date,
            r.mom_code,
            r.dad_code,
            r.mother_tank_label as mom_tank,
            r.father_tank_label as dad_tank,
            r.run_created_by    as created_by,
            r.run_created_at    as created_at,
            r.run_note          as note
          from public.vw_cross_runs_overview r
          where r.mom_code = :mom and r.dad_code = :dad
          order by r.run_created_at desc nulls last, r.cross_date desc nulls last
          limit 1000
        """)
        return pd.read_sql(q, cx, params={"mom": mom, "dad": dad})

any_found = False
for code in sel_codes:
    st.markdown(f"**{code}**")
    try:
        df_i = _fetch_instances_for_concept(code)
    except Exception as e:
        st.warning(f"Failed for {code}: {e}")
        continue

    if df_i.empty:
        st.caption("No instances.")
        continue

    any_found = True
    show = ["cross_run_code","cross_date","mom_code","dad_code",
            "mom_tank","dad_tank","created_by","created_at","note"]
    show = [c for c in show if c in df_i.columns]
    st.dataframe(df_i[show], use_container_width=True, hide_index=True)
    st.markdown("---")

if not any_found:
    st.info("No instance rows found for selected concept(s).")