from __future__ import annotations
import os, sys
from pathlib import Path
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ── path bootstrap ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Annotate Clutch Instances", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Clutch Instances")

# ── engine / env ────────────────────────────────────────────────────────────────
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set")
    st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

# DB badge (host + role) and capture user string for stamping
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

# (Optional) stamp app user into server-side session key app.user
try:
    from supabase.ui.lib.app_ctx import stamp_app_user
    who_ui = getattr(st.experimental_user, "email", "") if hasattr(st, "experimental_user") else ""
    if who_ui:
        user = who_ui  # prefer email if available
    stamp_app_user(eng, user)
except Exception:
    pass

# Ensure target table exists (we will write here)
with eng.begin() as cx:
    exists_tbl = cx.execute(text("select to_regclass('public.clutch_instances')")).scalar()
if not exists_tbl:
    st.error("Table public.clutch_instances not found in this DB.")
    st.stop()

# ── conceptual clutches (no date filters) ───────────────────────────────────────
st.markdown("## 🔍 Clutches — Conceptual overview")
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
        """),
        cx,
    )

# selection model for concepts
sel_key = "_concept_table"
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

st.markdown("### Conceptual clutches")
present_cols = [
    "✓ Select","clutch_code","clutch_name","clutch_nickname",
    "mom_code","dad_code","mom_code_tank","dad_code_tank","created_at",
]
present = [c for c in present_cols if c in st.session_state[sel_key].columns]
edited_concepts = st.data_editor(
    st.session_state[sel_key][present],
    hide_index=True,
    use_container_width=True,
    column_order=present,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
    key="ci_concept_editor",
)

# robust selection: read from session table; fallback to the first visible concept
try:
    _tbl = st.session_state.get("_concept_table")
    selected_codes = _tbl.loc[_tbl["✓ Select"]==True, "clutch_code"].astype(str).tolist()
except Exception:
    selected_codes = []
if not selected_codes and not st.session_state[sel_key].empty:
    try:
        selected_codes = [str(st.session_state[sel_key].iloc[0]["clutch_code"])]
    except Exception:
        selected_codes = []

# ── realized instances for selected concepts (no date filters) ──────────────────
st.markdown("### Realized instances for selection")
with eng.begin() as _cx_dbg:
    _host = (getattr(getattr(eng, "url", None), "host", None) or os.getenv("PGHOST", ""))
    _runs_cnt = pd.read_sql(text("select count(*) as c from public.vw_cross_runs_overview"), _cx_dbg)["c"].iloc[0]
    _sel_tbl = st.session_state.get("_concept_table")
    try:
        _checked = _sel_tbl.loc[_sel_tbl["✓ Select"]==True, "clutch_code"].astype(str).tolist() if isinstance(_sel_tbl, pd.DataFrame) else []
    except Exception:
        _checked = []
st.caption(f"DBG • host={_host} • runs_in_view={_runs_cnt} • checked_in_grid={_checked}")
st.caption(f"selected concepts used: {selected_codes}")

if not selected_codes:
    st.info("No realized clutch instances yet.")
else:
    with eng.begin() as cx:
        # selected concepts → mom/dad
        sel_mom_dad = pd.read_sql(
            text("""
                select conceptual_cross_code as clutch_code, mom_code, dad_code
                from public.v_cross_concepts_overview
                where conceptual_cross_code = any(:codes)
            """),
            cx, params={"codes": selected_codes}
        )
        # all runs (enriched)
        runs = pd.read_sql(
            text("""
                select
                  cross_instance_id,
                  cross_run_code,
                  cross_date::date as cross_date,
                  mom_code, dad_code,
                  mother_tank_label, father_tank_label
                from public.vw_cross_runs_overview
            """),
            cx
        )

    if sel_mom_dad.empty or runs.empty:
        st.info("No realized clutch instances yet.")
    else:
        # join by mom+dad
        det = sel_mom_dad.merge(runs, how="inner", on=["mom_code","dad_code"])
        det = det.sort_values(["cross_date"], ascending=[False])

        # minimal selection grid
        cols = [
            "clutch_code","cross_run_code","cross_date",
            "mom_code","dad_code","mother_tank_label","father_tank_label"
        ]
        present_det = [c for c in cols if c in det.columns]
        grid = det[present_det + (["cross_instance_id"] if "cross_instance_id" in det.columns else [])].copy()
        grid.insert(0, "✓ Add", False)
        edited_seed = st.data_editor(
            grid,
            hide_index=True,
            use_container_width=True,
            column_order=["✓ Add"] + present_det,
            column_config={"✓ Add": st.column_config.CheckboxColumn("✓", default=False)},
            key="ci_runs_editor_min",
        )

        # three text inputs (red, green, note) + count per run
        st.markdown("#### Quick annotate selected")
        c1, c2, c3, c4 = st.columns([1,1,3,1])
        with c1:
            red_txt = st.text_input("red", value="", placeholder="text")
        with c2:
            green_txt = st.text_input("green", value="", placeholder="text")
        with c3:
            note_txt = st.text_input("note", value="", placeholder="optional")

        if st.button("Submit"):
            sel = edited_seed[edited_seed["✓ Add"] == True]
            if sel.empty:
                st.warning("No runs selected.")
            else:
                saved = 0
                with eng.begin() as cx:
                    for _, r in sel.iterrows():
                        xid   = str(r.get("cross_instance_id") or "").strip()
                        ccode = str(r.get("clutch_code") or "").strip()
                        rcode = str(r.get("cross_run_code") or "").strip()
                        if not xid:
                            continue

                        base_label = " / ".join([s for s in (ccode, rcode) if s]) or "clutch"

                        existing = cx.execute(text("""
                            select count(*) from public.clutch_instances
                            where cross_instance_id = :xid
                        """), {"xid": xid}).scalar() or 0

                        suffix = f" [{existing + 1}]" if existing > 0 else ""
                        label  = base_label + suffix

                        cx.execute(text("""
                            insert into public.clutch_instances (
                                cross_instance_id, label, created_at,
                                red_intensity, green_intensity, notes,
                                red_selected, green_selected,
                                annotated_by, annotated_at
                            )
                            values (
                                :xid, :label, now(),
                                nullif(:red,''), nullif(:green,''), nullif(:note,''),
                                case when nullif(:red,'')   is not null then true else false end,
                                case when nullif(:green,'') is not null then true else false end,
                                coalesce(current_setting('app.user', true), :fallback_user),
                                now()
                            )
                        """), {
                            "xid": xid,
                            "label": label,
                            "red":   red_txt,
                            "green": green_txt,
                            "note":  note_txt,
                            "fallback_user": (user or "")
                        })
                        saved += 1

                st.success(f"Created {saved} clutch instance(s).")
                st.rerun()