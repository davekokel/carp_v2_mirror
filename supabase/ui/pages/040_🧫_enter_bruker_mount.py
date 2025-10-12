from __future__ import annotations
import os, sys
from pathlib import Path
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ── bootstrap ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Enter Bruker Mount", page_icon="🧫", layout="wide")
st.title("🧫 Enter Bruker Mount")

# ── engine / env ────────────────────────────────────────────────────────────────
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

# Stamp user for audit
user = ""
try:
    from supabase.ui.lib.app_ctx import stamp_app_user
    who_ui = getattr(st, "experimental_user", None)
    email  = getattr(who_ui, "email", "") if who_ui else ""
    with eng.begin() as cx:
        who  = cx.execute(text("select current_user")).scalar()
    user = email or (who or "")
    if user:
        stamp_app_user(eng, user)
except Exception:
    pass

# Ensure required tables exist
with eng.begin() as cx:
    have_ci  = bool(cx.execute(text("select to_regclass('public.clutch_instances')")).scalar())
    have_bm  = bool(cx.execute(text("select to_regclass('public.bruker_mounts')")).scalar())
    have_runs= bool(cx.execute(text("select to_regclass('public.vw_cross_runs_overview')")).scalar())
    have_cc  = bool(cx.execute(text("select to_regclass('public.v_cross_concepts_overview')")).scalar())
if not (have_ci and have_runs and have_cc):
    st.error("Required tables/views not found (clutch_instances / vw_cross_runs_overview / v_cross_concepts_overview).")
    st.stop()
if not have_bm:
    st.warning("Table public.bruker_mounts not found. Create it first (migration).")
    st.stop()

# ────────────────────────────────────────────────────────────────────────────────
# 1) Filter + select clutch concept (table + checkboxes)
# ────────────────────────────────────────────────────────────────────────────────
st.subheader("1) Choose clutch concept")

# Quick filter before the first table
f_col1, f_col2 = st.columns([2, 1])
with f_col1:
    concept_q = st.text_input("Filter concepts (code/name/mom/dad)", value="").strip()
with f_col2:
    max_rows = st.number_input("Show up to", min_value=50, max_value=2000, value=500, step=50)

with eng.begin() as cx:
    concepts = pd.read_sql(text("""
        select
          conceptual_cross_code as clutch_code,
          name                  as clutch_name,
          nickname              as clutch_nickname,
          mom_code, dad_code,
          created_at
        from public.v_cross_concepts_overview
        order by created_at desc nulls last, clutch_code
        limit :lim
    """), cx, params={"lim": int(max_rows)})

if concept_q:
    q = concept_q.lower()
    def _match(row) -> bool:
        vals = [
            str(row.get("clutch_code","")),
            str(row.get("clutch_name","")),
            str(row.get("mom_code","")),
            str(row.get("dad_code","")),
        ]
        return any(q in v.lower() for v in vals)
    concepts = concepts[concepts.apply(_match, axis=1)]

if concepts.empty:
    st.info("No concepts match your filter.")
    st.stop()

# Session model with ✓ column
key_concepts = "_bm_concepts_table"
if key_concepts not in st.session_state:
    t = concepts.copy()
    t.insert(0, "✓ Select", False)
    st.session_state[key_concepts] = t
else:
    base = st.session_state[key_concepts].set_index("clutch_code")
    now  = concepts.set_index("clutch_code")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[key_concepts] = base.reset_index()

concept_cols = [
    "✓ Select", "clutch_code", "clutch_name", "clutch_nickname",
    "mom_code", "dad_code", "created_at"
]
present = [c for c in concept_cols if c in st.session_state[key_concepts].columns]
edited_concepts = st.data_editor(
    st.session_state[key_concepts][present],
    hide_index=True, use_container_width=True,
    column_order=present,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
    key="bm_concepts_editor",
)
# persist ✓
st.session_state[key_concepts].loc[edited_concepts.index, "✓ Select"] = edited_concepts["✓ Select"]

selected_concepts = edited_concepts.loc[edited_concepts["✓ Select"]==True, "clutch_code"].astype(str).tolist()
if len(selected_concepts) == 0:
    st.info("Tick exactly one concept to continue.")
    st.stop()
if len(selected_concepts) > 1:
    st.warning("Please tick only one concept.")
    st.stop()

sel_clutch_code = selected_concepts[0]
row_concept = concepts.loc[concepts["clutch_code"]==sel_clutch_code].iloc[0]
mom_code, dad_code = str(row_concept["mom_code"]), str(row_concept["dad_code"])

# ────────────────────────────────────────────────────────────────────────────────
# 2) Select cross instance (runs table + checkboxes)
# ────────────────────────────────────────────────────────────────────────────────
st.subheader("2) Choose cross instance (run) for the concept")

with eng.begin() as cx:
    runs = pd.read_sql(text("""
        select
          cross_instance_id,
          cross_run_code,
          cross_date::date as cross_date,
          mother_tank_label, father_tank_label
        from public.vw_cross_runs_overview
        where mom_code=:mom and dad_code=:dad
        order by cross_date desc nulls last, cross_run_code desc
    """), cx, params={"mom": mom_code, "dad": dad_code})

if runs.empty:
    st.info("No runs for this concept.")
    st.stop()

key_runs = "_bm_runs_table"
if key_runs not in st.session_state:
    t = runs.copy()
    t.insert(0, "✓ Select", False)
    st.session_state[key_runs] = t
else:
    base = st.session_state[key_runs].set_index("cross_run_code")
    now  = runs.set_index("cross_run_code")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[key_runs] = base.reset_index()

run_cols = [
    "✓ Select", "cross_run_code", "cross_date",
    "mother_tank_label", "father_tank_label"
]
present = [c for c in run_cols if c in st.session_state[key_runs].columns]
edited_runs = st.data_editor(
    st.session_state[key_runs][present],
    hide_index=True, use_container_width=True,
    column_order=present,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
    key="bm_runs_editor",
)
st.session_state[key_runs].loc[edited_runs.index, "✓ Select"] = edited_runs["✓ Select"]

selected_runs = edited_runs.loc[edited_runs["✓ Select"]==True]
if len(selected_runs) == 0:
    st.info("Tick exactly one run to continue.")
    st.stop()
if len(selected_runs) > 1:
    st.warning("Please tick only one run.")
    st.stop()

sel_run_code = str(selected_runs.iloc[0]["cross_run_code"])
sel_xid      = str(
    runs.loc[runs["cross_run_code"]==sel_run_code, "cross_instance_id"].iloc[0]
)
sel_run_date = runs.loc[runs["cross_run_code"]==sel_run_code, "cross_date"].iloc[0]

# ────────────────────────────────────────────────────────────────────────────────
# 3) Select an existing selection (clutch_instances) via table + checkboxes
# ────────────────────────────────────────────────────────────────────────────────
st.subheader("3) Choose an annotated selection for this run")

with eng.begin() as cx:
    selections = pd.read_sql(text("""
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
    """), cx, params={"xid": sel_xid})

if selections.empty:
    st.info("No selections on this run. Use the annotate page to create one, then return.")
    st.stop()

key_selections = "_bm_sel_table"
if key_selections not in st.session_state:
    t = selections.copy()
    t.insert(0, "✓ Select", False)
    st.session_state[key_selections] = t
else:
    base = st.session_state[key_selections].set_index("id")
    now  = selections.set_index("id")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[key_selections] = base.reset_index()

sel_cols = [
    "✓ Select", "when_at", "label",
    "red_intensity", "green_intensity", "notes", "annotated_by", "id"
]
present = [c for c in sel_cols if c in st.session_state[key_selections].columns]
edited_sel = st.data_editor(
    st.session_state[key_selections][present],
    hide_index=True, use_container_width=True,
    column_order=present,
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "id": st.column_config.TextColumn("selection_id", disabled=True),
    },
    key="bm_sel_editor",
)
st.session_state[key_selections].loc[edited_sel.index, "✓ Select"] = edited_sel["✓ Select"]

picked = edited_sel.loc[edited_sel["✓ Select"]==True]
if len(picked) == 0:
    st.info("Tick exactly one selection to continue.")
    st.stop()
if len(picked) > 1:
    st.warning("Please tick only one selection.")
    st.stop()

selection_id    = str(picked.iloc[0]["id"])
selection_label = str(picked.iloc[0]["label"] or "")

st.caption(f"Context • concept={sel_clutch_code} • run={sel_run_code} ({sel_run_date}) • selection_label={selection_label}")

# ────────────────────────────────────────────────────────────────────────────────
# 4) Enter mount fields and Save
# ────────────────────────────────────────────────────────────────────────────────
st.subheader("4) Mount details")

c1, c2, c3 = st.columns([1,1,1])
with c1:
    mount_date = st.date_input("Date", value=dt.date.today())
with c2:
    mount_time = st.time_input("Time mounted", value=dt.datetime.now().time().replace(second=0, microsecond=0))
with c3:
    orientation = st.selectbox(
        "Orientation",
        ["dorsal","ventral","left","right","front","back","other"],
        index=0
    )

c4, c5 = st.columns([1,1])
with c4:
    n_top = st.number_input("n_top", min_value=0, value=0, step=1)
with c5:
    n_bottom = st.number_input("n_bottom", min_value=0, value=0, step=1)

if st.button("Save mount", type="primary"):
    if not selection_id:
        st.warning("Pick a selection first.")
    else:
        try:
            with eng.begin() as cx:
                cx.execute(text("""
                    insert into public.bruker_mounts (
                      selection_id, mount_date, mount_time, n_top, n_bottom, orientation, created_by
                    )
                    values (
                      cast(:sel as uuid), :d, :t, :nt, :nb, :ori,
                      coalesce(current_setting('app.user', true), :who)
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

# ────────────────────────────────────────────────────────────────────────────────
# 5) Recent mounts for the chosen selection (confirmation)
# ────────────────────────────────────────────────────────────────────────────────
st.markdown("### Recent mounts for this selection")
with eng.begin() as cx:
    mounts = pd.read_sql(text("""
        select
          id,
          mount_date, mount_time,
          n_top, n_bottom, orientation,
          created_at, created_by
        from public.bruker_mounts
        where selection_id = cast(:sel as uuid)
        order by created_at desc
        limit 50
    """), cx, params={"sel": selection_id})

if mounts.empty:
    st.caption("No mounts yet for this selection.")
else:
    st.dataframe(mounts, hide_index=True, use_container_width=True)