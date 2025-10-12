from __future__ import annotations
import os, sys
from pathlib import Path
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# bootstrap
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Enter Bruker Mount", page_icon="🧫", layout="wide")
st.title("🧫 Enter Bruker Mount")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

# stamp app user (optional)
user = ""
try:
    from supabase.ui.lib.app_ctx import stamp_app_user
    who_ui = getattr(st, "experimental_user", None)
    email  = getattr(who_ui, "email", "") if who_ui else ""
    with eng.begin() as cx:
        who  = cx.execute(text("select current_user")).scalar()
    user = email or who or ""
    if user:
        stamp_app_user(eng, user)
except Exception:
    pass

# 1) pick a clutch concept
st.subheader("1) Select clutch concept")
with eng.begin() as cx:
    df_concepts = pd.read_sql(text("""
        select
          conceptual_cross_code as clutch_code,
          name as clutch_name,
          mom_code, dad_code,
          created_at
        from public.v_cross_concepts_overview
        order by created_at desc nulls last, clutch_code
        limit 500
    """), cx)
if df_concepts.empty:
    st.info("No clutch concepts found."); st.stop()

codes = df_concepts["clutch_code"].astype(str).tolist()
labels = [f"{r.clutch_code} — {r.clutch_name or ''}".strip() for r in df_concepts.itertuples(index=False)]
sel_concept = st.selectbox("Clutch concept", labels, index=0)
clutch_code = codes[labels.index(sel_concept)]
row_concept = df_concepts.loc[df_concepts["clutch_code"]==clutch_code].iloc[0]
mom_code, dad_code = str(row_concept["mom_code"]), str(row_concept["dad_code"])

# 2) select run (cross instance)
st.subheader("2) Select cross instance (run)")
with eng.begin() as cx:
    df_runs = pd.read_sql(text("""
        select
          cross_instance_id,
          cross_run_code,
          cross_date::date as cross_date,
          mother_tank_label, father_tank_label
        from public.vw_cross_runs_overview
        where mom_code=:mom and dad_code=:dad
        order by cross_date desc nulls last, cross_run_code desc
    """), cx, params={"mom": mom_code, "dad": dad_code})
if df_runs.empty:
    st.info("No runs for this concept."); st.stop()

run_labels = [f"{r.cross_run_code} — {r.cross_date}" for r in df_runs.itertuples(index=False)]
sel_run = st.selectbox("Cross instance (run)", run_labels, index=0)
xid = str(df_runs.iloc[run_labels.index(sel_run)]["cross_instance_id"])
run_code = str(df_runs.iloc[run_labels.index(sel_run)]["cross_run_code"])
run_date = df_runs.iloc[run_labels.index(sel_run)]["cross_date"]

# 3) pick an annotated selection (clutch_instances row)
st.subheader("3) Select annotated clutch selection")
with eng.begin() as cx:
    df_sel = pd.read_sql(text("""
        select
          id,
          label,
          coalesce(annotated_at, created_at) as when_at,
          coalesce(red_intensity,'')   as red_intensity,
          coalesce(green_intensity,'') as green_intensity,
          coalesce(notes,'')           as notes,
          annotated_by
        from public.clutch_instances
        where cross_instance_id = cast(:xid as uuid)
        order by coalesce(annotated_at, created_at) desc, created_at desc
    """), cx, params={"xid": xid})

if df_sel.empty:
    st.info("No selections found for this run. Create a selection first on the annotate page."); st.stop()

sel_labels = [
    f"{r.when_at.strftime('%Y-%m-%d %H:%M')} — {r.label} — red={r.red_intensity} green={r.green_intensity} note={r.notes}"
    for r in df_sel.itertuples(index=False)
]
pick = st.selectbox("Annotated selection", sel_labels, index=0)
selection_id = str(df_sel.iloc[sel_labels.index(pick)]["id"])
selection_label = str(df_sel.iloc[sel_labels.index(pick)]["label"])

# 4) enter mount fields
st.subheader("4) Mount details")
c1, c2, c3 = st.columns([1,1,1])
with c1:
    mount_date = st.date_input("Date", value=dt.date.today())
with c2:
    mount_time = st.time_input("Time mounted", value=dt.datetime.now().time().replace(second=0, microsecond=0))
with c3:
    orientation = st.selectbox("Orientation", ["dorsal","ventral","left","right","front","back","other"], index=0)

c4, c5 = st.columns([1,1])
with c4:
    n_top = st.number_input("n_top", min_value=0, value=0, step=1)
with c5:
    n_bottom = st.number_input("n_bottom", min_value=0, value=0, step=1)

st.caption(f"Context • concept={clutch_code} • run={run_code} ({run_date}) • selection_label={selection_label}")

# 5) save
if st.button("Save mount", type="primary"):
    try:
        with eng.begin() as cx:
            cx.execute(text("""
                insert into public.bruker_mounts (
                  selection_id, mount_date, mount_time, n_top, n_bottom, orientation, created_by
                )
                values (
                  cast(:sel as uuid), :d, :t, :nt, :nb, :ori, coalesce(current_setting('app.user', true), :who)
                )
            """), {
                "sel": selection_id,
                "d": str(mount_date),
                "t": mount_time.strftime("%H:%M:%S"),
                "nt": int(n_top),
                "nb": int(n_bottom),
                "ori": orientation,
                "who": user
            })
        st.success("Bruker mount saved.")
    except Exception as e:
        st.error(f"Failed to save: {e}")