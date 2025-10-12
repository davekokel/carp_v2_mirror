from __future__ import annotations
import os, sys
from pathlib import Path
import datetime as _dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# Path bootstrap
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Annotate Clutch Instances", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Clutch Instances")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

# DB badge (host + role)
from sqlalchemy import text as _text
try:
    url = getattr(eng, "url", None)
    host = (getattr(url, "host", None) or os.getenv("PGHOST", "") or "(unknown)")
    with eng.begin() as cx:
        role = cx.execute(_text("select current_setting('role', true)")).scalar()
        user = cx.execute(_text("select current_user")).scalar()
    st.caption(f"DB: {host} • role={role or 'default'} • user={user}")
except Exception:
    pass

# Stamp user into session (for audit)
try:
    from supabase.ui.lib.app_ctx import stamp_app_user
    who = getattr(st.experimental_user, "email", "") if hasattr(st, "experimental_user") else ""
    stamp_app_user(eng, who)
except Exception:
    pass

# Ensure clutch_instances exists (this is where we write)
with eng.begin() as cx:
    exists_tbl = cx.execute(text("select to_regclass('public.clutch_instances')")).scalar()
if not exists_tbl:
    st.error("Table public.clutch_instances not found in this DB.")
    st.stop()

# ───────────────────── Conceptual overview ─────────────────────
st.markdown("## 🔍 Clutches — Conceptual overview with instance counts")

today = _dt.date.today()
d_from = st.date_input("From", value=today - _dt.timedelta(days=14), key="ci_from")
d_to   = st.date_input("To",   value=today,                      key="ci_to")
if d_from and d_to and d_from > d_to:
    d_from, d_to = d_to, d_from

# Load concepts in window
with eng.begin() as cx:
    concept_df = pd.read_sql(
        text("""
            select
              conceptual_cross_code as clutch_code,
              name as clutch_name,
              nickname as clutch_nickname,
              mom_code, dad_code, mom_code_tank, dad_code_tank,
              created_at
            from public.v_cross_concepts_overview
            where (:d1 is null or created_at::date >= :d1)
              and (:d2 is null or created_at::date <= :d2)
            order by created_at desc nulls last, clutch_code
            limit 2000
        """),
        cx,
        params={"d1": str(d_from) if d_from else None, "d2": str(d_to) if d_to else None},
    )

# Count realized runs in window (match by mom+dad)
counts = pd.DataFrame(columns=["clutch_code", "n_instances"])
if not concept_df.empty:
    with eng.begin() as cx:
        runs = pd.read_sql(
            text("""
                select cross_run_code, cross_date::date as d, mom_code, dad_code
                from public.vw_cross_runs_overview
                where (:d1 is null or cross_date::date >= :d1)
                  and (:d2 is null or cross_date::date <= :d2)
            """),
            cx,
            params={"d1": str(d_from) if d_from else None, "d2": str(d_to) if d_to else None},
        )
    if not runs.empty:
        merged = concept_df.merge(runs, how="left", on=["mom_code","dad_code"])
        counts = (
            merged.groupby("clutch_code", dropna=False)["cross_run_code"]
            .count().rename("n_instances").reset_index()
        )
concept_df = concept_df.merge(counts, how="left", on="clutch_code").fillna({"n_instances": 0})
concept_df = concept_df.astype({"n_instances": int})

# Selection model for concepts
sel_key = "_concept_table"
if sel_key not in st.session_state:
    t = concept_df.copy(); t.insert(0, "✓ Select", False); st.session_state[sel_key] = t
else:
    base = st.session_state[sel_key].set_index("clutch_code")
    now  = concept_df.set_index("clutch_code")
    for i in now.index:
        if i not in base.index: base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[sel_key] = base.reset_index()

st.markdown("### Conceptual clutches")
view_cols = [
    "✓ Select","clutch_code","clutch_name","clutch_nickname",
    "mom_code","dad_code","mom_code_tank","dad_code_tank","created_at","n_instances",
]
present = [c for c in view_cols if c in st.session_state[sel_key].columns]
edited_concepts = st.data_editor(
    st.session_state[sel_key][present],
    hide_index=True, use_container_width=True,
    column_order=present,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
    key="ci_concept_editor",
)
st.session_state[sel_key].loc[edited_concepts.index, "✓ Select"] = edited_concepts["✓ Select"]
selected_codes = edited_concepts.loc[edited_concepts["✓ Select"], "clutch_code"].astype(str).tolist()

# ───────────────────── Realized instances for selected concepts ─────────────────────
st.markdown("### Realized instances for selection")

if not selected_codes:
    st.info("No realized clutch instances yet.")
else:
    with eng.begin() as cx:
        sel_mom_dad = pd.read_sql(
            text("""
                select conceptual_cross_code as clutch_code, mom_code, dad_code
                from public.v_cross_concepts_overview
                where conceptual_cross_code = any(:codes)
            """),
            cx, params={"codes": selected_codes}
        )
        runs = pd.read_sql(
            text("""
                select
                  cross_instance_id,
                  cross_run_code,
                  cross_date::date as cross_date,
                  mom_code, dad_code,
                  mother_tank_label, father_tank_label
                from public.vw_cross_runs_overview
                where (:d1 is null or cross_date::date >= :d1)
                  and (:d2 is null or cross_date::date <= :d2)
            """),
            cx, params={"d1": str(d_from) if d_from else None, "d2": str(d_to) if d_to else None}
        )

    if sel_mom_dad.empty or runs.empty:
        st.info("No realized clutch instances yet.")
    else:
        det = sel_mom_dad.merge(runs, how="inner", on=["mom_code","dad_code"])
        det = det.sort_values(["cross_date"], ascending=[False])

        # Minimal selection grid
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

        # three text inputs (red, green, note) + submit
        st.markdown("#### Quick annotate selected")
        c1, c2, c3 = st.columns([1, 1, 3])
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
                        xid = str(r.get("cross_instance_id") or "").strip()
                        ccode = str(r.get("clutch_code") or "").strip()
                        rcode = str(r.get("cross_run_code") or "").strip()
                        if not xid:
                            continue
                        label = " / ".join([s for s in (ccode, rcode) if s]) or "clutch"

                        # Insert if missing
                        cx.execute(text("""
                            insert into public.clutch_instances (cross_instance_id, label, created_at)
                            select :xid, :label, now()
                            where not exists (
                              select 1 from public.clutch_instances where cross_instance_id = :xid
                            )
                        """), {"xid": xid, "label": label})

                        # Update fields (text inputs) + stamp
                        cx.execute(text("""
                            update public.clutch_instances
                               set red_intensity   = nullif(:red, ''),
                                   green_intensity = nullif(:green, ''),
                                   notes           = nullif(:note, ''),
                                   red_selected    = case when nullif(:red, '') is not null then true else false end,
                                   green_selected  = case when nullif(:green, '') is not null then true else false end,
                                   annotated_by    = coalesce(current_setting('app.user', true), annotated_by),
                                   annotated_at    = now()
                             where cross_instance_id = :xid
                        """), {"xid": xid, "red": red_txt, "green": green_txt, "note": note_txt})
                        saved += 1
                st.success(f"Saved {saved} annotation(s).")
                st.rerun()