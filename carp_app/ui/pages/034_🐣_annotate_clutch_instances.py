from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

import os, re
from pathlib import Path
from datetime import date, timedelta
from typing import List

import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Annotate Clutch Instances", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Clutch Instances")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

try:
    from sqlalchemy import text as _text
    url = getattr(eng, "url", None)
    host = (getattr(url, "host", None) or os.getenv("PGHOST", "") or "(unknown)")
    with eng.begin() as cx:
        role = cx.execute(_text("select current_setting('role', true)")).scalar()
        who  = cx.execute(_text("select current_user")).scalar()
    st.caption(f"DB: {host} • role={role or 'default'} • user={who or ''}")
    app_user = (who or "")
except Exception:
    app_user = ""

try:
    from carp_app.ui.lib.app_ctx import stamp_app_user
    who_ui = getattr(st.experimental_user, "email", "") if hasattr(st, "experimental_user") else ""
    if who_ui:
        app_user = who_ui
    stamp_app_user(eng, app_user)
except Exception:
    pass

with eng.begin() as cx:
    exists_tbl = cx.execute(text("select to_regclass('public.clutch_instances')")).scalar()
if not exists_tbl:
    st.error("Table public.clutch_instances not found in this DB.")
    st.stop()

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
if concept_df.empty:
    st.info("No clutch concepts found."); st.stop()

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
st.session_state[sel_key].loc[edited_concepts.index, "✓ Select"] = edited_concepts["✓ Select"]

tbl = st.session_state.get(sel_key)
selected_codes: List[str] = []
if isinstance(tbl, pd.DataFrame):
    selected_codes = tbl.loc[tbl["✓ Select"] == True, "clutch_code"].astype(str).tolist()

if not selected_codes:
    st.info("Tick one or more clutches above to show realized instances.")
    st.stop()

st.markdown("### Realized instances for selection")

with st.form("date_filters", clear_on_submit=False):
    today = date.today()
    c1, c2 = st.columns([1,1])
    with c1:
        d_from = st.date_input("From", value=today - timedelta(days=30))
    with c2:
        d_to   = st.date_input("To", value=today)
    st.form_submit_button("Apply", use_container_width=True)

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
        """),
        cx
    )
    cl_map = pd.read_sql(
        text("""
            select
              ci.id             as cross_instance_id,
              coalesce(cl.clutch_code, cp.clutch_code) as clutch_code
            from public.cross_instances ci
            left join public.clutches cl        on cl.cross_instance_id = ci.id
            left join public.planned_crosses pc on pc.cross_id = ci.cross_id
            left join public.clutch_plans   cp on cp.id = pc.clutch_id
        """),
        cx
    )
    agg = pd.read_sql(
        text("""
            select
              cross_instance_id,
              max(annotated_at)::date as day_annotated,
              string_agg(
                trim(
                  concat_ws(' ',
                    case when coalesce(red_intensity,'')   <> '' then 'red='   || red_intensity   end,
                    case when coalesce(green_intensity,'') <> '' then 'green=' || green_intensity end,
                    case when coalesce(notes,'')           <> '' then 'note='  || notes          end
                  )
                ),
                ' | ' order by created_at
              ) as annotations_rollup
            from public.clutch_instances
            group by cross_instance_id
        """),
        cx
    )

if sel_mom_dad.empty or runs.empty:
    st.info("No realized clutch instances yet."); st.stop()

# Build realized table
det = sel_mom_dad.merge(runs, how="inner", on=["mom_code","dad_code"]).sort_values("cross_date", ascending=False)

# Try to bring in clutch_code from clutches/plans (cl_map)
if not cl_map.empty:
    det = det.merge(cl_map, how="left", on="cross_instance_id")

# Normalize clutch_code so it always exists
if "clutch_code_x" in det.columns and "clutch_code_y" in det.columns:
    det["clutch_code"] = det["clutch_code_y"].fillna(det["clutch_code_x"])
    det.drop(columns=["clutch_code_x","clutch_code_y"], inplace=True)
elif "clutch_code_y" in det.columns:
    det["clutch_code"] = det["clutch_code_y"]
    det.drop(columns=["clutch_code_y"], inplace=True)
elif "clutch_code_x" in det.columns:
    det["clutch_code"] = det["clutch_code_x"]
    det.drop(columns=["clutch_code_x"], inplace=True)
elif "clutch_code" not in det.columns:
    det["clutch_code"] = pd.Series("", index=det.index)

# Attach aggregates if present
if not agg.empty:
    det = det.merge(agg, how="left", on="cross_instance_id")

# Derive birthday and clean types
det["birthday"] = det["cross_date"]
det["day_annotated"] = det.get("day_annotated", pd.Series([pd.NaT]*len(det))).astype("string")
det["annotations_rollup"] = det.get("annotations_rollup", pd.Series([""]*len(det))).fillna("").astype("string")

# Apply date filters safely (work even if day_annotated has blanks)
_annot_dates = pd.to_datetime(det["day_annotated"], errors="coerce").dt.date
date_mask = det["cross_date"].between(d_from, d_to) | _annot_dates.between(d_from, d_to)

# Filter by selected concept code
code_mask = det["clutch_code"].isin(selected_codes)

det = det[date_mask & code_mask]

present_det = [c for c in cols if c in det.columns]
grid_cols = present_det + (["cross_instance_id"] if "cross_instance_id" in det.columns else [])
runs_grid = det[grid_cols].copy()
runs_grid.insert(0, "✓ Add", False)

edited_seed = st.data_editor(
    runs_grid,
    hide_index=True,
    use_container_width=True,
    column_order=["✓ Add"] + present_det,
    column_config={"✓ Add": st.column_config.CheckboxColumn("✓", default=False)},
    key="ci_runs_editor_min",
)

st.markdown("#### Existing selections for the checked run(s)")
checked_xids: List[str] = []
if "cross_instance_id" in edited_seed.columns:
    checked_xids = (
        edited_seed.loc[edited_seed["✓ Add"] == True, "cross_instance_id"]
        .dropna().astype(str).unique().tolist()
    )

uuid_re = re.compile(r"^[0-9a-fA-F-]{36}$")
safe_xids = [x for x in checked_xids if uuid_re.match(x)]
if not safe_xids:
    st.info("Select a run in the table above to view its existing selections.")
else:
    values_sql = ", ".join([f"(uuid '{x}')" for x in safe_xids])
    sql = f"""
        with picked(id) as (values {values_sql})
        select
          ci.id            as selection_id,
          ci.cross_instance_id,
          ci.created_at    as selection_created_at,
          ci.annotated_at  as selection_annotated_at,
          ci.red_intensity,
          ci.green_intensity,
          ci.notes,
          ci.annotated_by,
          ci.label
        from public.clutch_instances ci
        join picked p on p.id = ci.cross_instance_id
        order by coalesce(ci.annotated_at, ci.created_at) desc,
                 ci.created_at desc
    """
    with eng.begin() as cx:
        sel_rows = pd.read_sql(sql, cx)

    run_meta = det[["cross_instance_id","clutch_code","cross_run_code","birthday"]].drop_duplicates()
    table = sel_rows.merge(run_meta, how="left", on="cross_instance_id")

    show_cols = [
        "clutch_code","cross_run_code","birthday",
        "selection_created_at","selection_annotated_at",
        "red_intensity","green_intensity","notes","annotated_by","label","selection_id",
    ]
    present = [c for c in show_cols if c in table.columns]
    st.dataframe(table[present], hide_index=True, use_container_width=True)

st.markdown("#### Quick annotate selected")
c1, c2, c3 = st.columns([1,1,3])
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
                if not xid or not uuid_re.match(xid):
                    continue
                base_label = " / ".join([s for s in (ccode, rcode) if s]) or "clutch"
                existing = cx.execute(
                    text("select count(*) from public.clutch_instances where cross_instance_id = cast(:xid as uuid)"),
                    {"xid": xid}
                ).scalar_one_or_none() or 0
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
                        cast(:xid as uuid), :label, now(),
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
                    "fallback_user": (app_user or "")
                })
                saved += 1
        st.success(f"Created {saved} clutch instance(s).")
        st.rerun()

st.markdown("### Selection instances (distinct)")
if "cross_instance_id" not in det.columns:
    st.caption("View does not expose cross_instance_id; cannot list selections.")
else:
    xids_all = det["cross_instance_id"].dropna().astype(str).unique().tolist()
    safe_all = [x for x in xids_all if uuid_re.match(x)]
    if not safe_all:
        st.info("No selection instances yet for the selected runs.")
    else:
        values_all = ", ".join([f"(uuid '{x}')" for x in safe_all])
        sql_all = f"""
            with picked(id) as (values {values_all})
            select
              ci.id           as selection_id,
              ci.cross_instance_id,
              ci.created_at   as selection_created_at,
              ci.annotated_at as selection_annotated_at,
              ci.red_intensity,
              ci.green_intensity,
              ci.notes,
              ci.annotated_by,
              ci.label
            from public.clutch_instances ci
            join picked p on p.id = ci.cross_instance_id
            order by coalesce(ci.annotated_at, ci.created_at) desc,
                     ci.created_at desc
        """
        with eng.begin() as cx:
            table_all = pd.read_sql(sql_all, cx)
        run_meta = det[["cross_instance_id","clutch_code","cross_run_code","birthday"]].drop_duplicates()
        if not table_all.empty:
            table_all = table_all.merge(run_meta, how="left", on="cross_instance_id")
        cols = [
            "clutch_code","cross_run_code","birthday",
            "selection_created_at","selection_annotated_at",
            "red_intensity","green_intensity","notes","annotated_by","label","selection_id",
        ]
        present = [c for c in cols if c in table_all.columns]
        st.dataframe(table_all[present], hide_index=True, use_container_width=True)