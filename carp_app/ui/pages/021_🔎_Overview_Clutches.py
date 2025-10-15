from carp_app.lib.config import engine as get_engine
from __future__ import annotations
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

import os, sys
from pathlib import Path
import pandas as pd
import streamlit as st
from carp_app.lib.db import get_engine, text

# ── path bootstrap ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="Clutches — Conceptual overview with instance counts",
    page_icon="🧬",
    layout="wide",
)
st.title("🧬 Clutches — Conceptual overview with instance counts")

# ── engine / env ────────────────────────────────────────────────────────────────
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

# DB badge (host + role) + capture user
user = ""
try:
    url = getattr(eng, "url", None)
    host = (getattr(url, "host", None) or os.getenv("PGHOST", "") or "(unknown)")
    with eng.begin() as cx:
        role = cx.execute(text("select current_setting('role', true)")).scalar()
        who  = cx.execute(text("select current_user")).scalar() or ""
    user = who
    st.caption(f"DB: {host} • role={role or 'none'} • user={user}")
except Exception:
    pass

# ── conceptual clutches (no date filters) ───────────────────────────────────────
st.markdown("## Conceptual clutches")
with eng.begin() as cx:
    concept_df = pd.read_sql(
        text("""
            select
              conceptual_cross_code as clutch_code,
              name                  as clutch_name,
              nickname              as clutch_nickname,
              mom_code, dad_code, mom_code_tank, dad_code_tank,
              created_at
            from public.v_cross_concepts_overview
            order by created_at desc nulls last, clutch_code
            limit 2000
        """), cx)

# selection model for concepts (checkbox grid)
sel_key = "_concept_table_overview"
if sel_key not in st.session_state:
    t = concept_df.copy()
    t.insert(0, "✓ Select", False)
    st.session_state[sel_key] = t
else:
    base = st.session_state[sel_key].set_index("clutch_code")
    now  = concept_df.set_index("clutch_code")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[sel_key] = base.reset_index()

present_cols = [
    "✓ Select","clutch_code","clutch_name","clutch_nickname",
    "mom_code","dad_code","mom_code_tank","dad_code_tank","created_at",
]
present = [c for c in present_cols if c in st.session_state[sel_key].columns]
_edited_concepts = st.data_editor(
    st.session_state[sel_key][present],
    hide_index=True, use_container_width=True, column_order=present,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
    key="ov_concept_editor",
)
# ✅ persist ✓ back to the session model
st.session_state[sel_key].loc[_edited_concepts.index, "✓ Select"] = _edited_concepts["✓ Select"]

# ───────────────────────── Realized instances for selected concepts ─────────────────────────
st.markdown("### Realized instances for selection")

# Debug banner: host, runs in view, and what's checked in the grid
with eng.begin() as _cx_dbg:
    _host = (getattr(getattr(eng, "url", None), "host", None) or os.getenv("PGHOST", ""))
    _runs_cnt = pd.read_sql(text("select count(*) as c from public.vw_cross_runs_overview"), _cx_dbg)["c"].iloc[0]
    _sel_tbl = st.session_state.get(sel_key)
    try:
        _checked = _sel_tbl.loc[_sel_tbl["✓ Select"] == True, "clutch_code"].astype(str).tolist() \
                   if isinstance(_sel_tbl, pd.DataFrame) else []
    except Exception:
        _checked = []
st.caption(f"DBG • host={_host} • runs_in_view={_runs_cnt} • checked_in_grid={_checked}")

# ❗STRICT selection: require at least one ✓; no fallback
selected_codes: list[str] = []
tbl = st.session_state.get(sel_key)
if isinstance(tbl, pd.DataFrame):
    selected_codes = (
        tbl.loc[tbl["✓ Select"] == True, "clutch_code"].astype(str).tolist()
    )

st.caption(f"selected concepts used: {selected_codes}")

if not selected_codes:
    st.info("Tick one or more clutches above to show realized instances.")
    st.stop()

# Load selected mom/dad and all runs (NO date filter), then match by mom+dad
with eng.begin() as cx:
    sel_mom_dad = pd.read_sql(
        text("""
            select conceptual_cross_code as clutch_code,
                   mom_code, dad_code
            from public.v_cross_concepts_overview
            where conceptual_cross_code = any(:codes)
        """), cx, params={"codes": selected_codes}
    )
    runs = pd.read_sql(
        text("""
            select
              cross_instance_id,
              cross_run_code,
              cross_date::date as cross_date,
              mom_code, dad_code,
              mother_tank_label, father_tank_label,
              run_created_by, run_created_at, run_note
            from public.vw_cross_runs_overview
        """), cx)

if sel_mom_dad.empty or runs.empty:
    st.info("No realized clutch instances yet."); st.stop()

det = sel_mom_dad.merge(runs, how="inner", on=["mom_code","dad_code"]).sort_values(
    ["run_created_at","cross_date"], ascending=[False, False]
)
st.caption(f"matched by mom+dad: {len(det)}")

# --- Pull aggregated annotations per run from clutch_instances (by cross_instance_id)
with eng.begin() as cx:
    ci_df = pd.read_sql(
        text("""
            select
              cross_instance_id,
              max(annotated_at)::date as day_annotated,
              string_agg(
                trim(
                  concat(
                    case when coalesce(red_intensity,'')   <> '' then 'red='   || red_intensity   else null end,
                    case when coalesce(green_intensity,'') <> '' then ' green='|| green_intensity else null end,
                    case when coalesce(notes,'')           <> '' then ' note=' || notes          else null end
                  )
                ),
                ' | ' order by created_at
              ) as annotations
            from public.clutch_instances
            group by cross_instance_id
        """), cx
    )

# Left-merge aggregated annotations onto the matched runs by cross_instance_id (if that column exists)
if "cross_instance_id" in det.columns and not ci_df.empty:
    en = det.merge(ci_df, how="left", on="cross_instance_id")
else:
    en = det.copy()
    if "cross_instance_id" not in en.columns:
        # placeholder if the view doesn't expose it
        en["cross_instance_id"] = None
    en["day_annotated"] = pd.NaT
    en["annotations"]  = ""

# Compute the requested presentation columns
en["clutch_genotype"] = en["mom_code"].astype(str) + " × " + en["dad_code"].astype(str)
# treatments rollup: use run_note from runs (blank if none)
en["treatments"]      = en.get("run_note", pd.Series([""]*len(en))).fillna("")
# birthday = cross_date
en["birthday"]        = en["cross_date"]

# Show only the requested columns in the requested order
show_cols = [
    "clutch_code",
    "cross_run_code",
    "clutch_genotype",
    "treatments",
    "birthday",
    "day_annotated",
    "annotations",
]

present = [c for c in show_cols if c in en.columns]
st.dataframe(
    en[present],
    use_container_width=True,
    hide_index=True
)
