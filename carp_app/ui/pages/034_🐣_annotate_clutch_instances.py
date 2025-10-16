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
    has_view = cx.execute(text("select to_regclass('public.v_clutch_instances_overview')")).scalar()
    has_tbl  = cx.execute(text("select to_regclass('public.clutch_instances')")).scalar()
if not has_tbl:
    st.error("Table public.clutch_instances not found in this DB.")
    st.stop()
if not has_view:
    st.error("View public.v_clutch_instances_overview not found. Run the migration first.")
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

def _load_realized(engine, codes: List[str], d_from: date, d_to: date) -> pd.DataFrame:
    sql = text("""
        select
          clutch_code,
          cross_run_code,
          birthday,
          day_annotated,
          annotations_rollup,
          mom_code,
          dad_code,
          mother_tank_code,
          father_tank_code,
          clutch_name,
          clutch_nickname
        from public.v_clutch_instances_overview
        where clutch_code = any(:codes)
          and birthday >= :from_date::date
          and birthday <  (:to_date::date + interval '1 day')
        order by birthday desc
        limit 2000
    """)
    with engine.begin() as cx:
        rows = pd.read_sql(sql, cx, params={"codes": selected_codes, "from_date": str(d_from), "to_date": str(d_to)})
    return rows

realized = _load_realized(eng, selected_codes, d_from, d_to)
if realized.empty:
    st.info("No realized clutch instances in this window."); st.stop()

cols = [
    "clutch_code","cross_run_code","birthday",
    "day_annotated","annotations_rollup",
    "mom_code","dad_code","mother_tank_code","father_tank_code",
]
present_det = [c for c in cols if c in realized.columns]
grid = realized[present_det].copy()
grid.insert(0, "✓ Add", False)

edited_seed = st.data_editor(
    grid,
    hide_index=True,
    use_container_width=True,
    column_order=["✓ Add"] + present_det,
    column_config={"✓ Add": st.column_config.CheckboxColumn("✓", default=False)},
    key="ci_runs_editor_from_view",
)

st.markdown("#### Existing selections for the checked run(s)")
checked = edited_seed.loc[edited_seed["✓ Add"] == True]
uuid_re = re.compile(r"^[0-9a-fA-F-]{36}$")

def _resolve_cross_instance_ids(engine, rows: pd.DataFrame) -> List[str]:
    if rows.empty:
        return []
    codes = rows["cross_run_code"].dropna().astype(str).unique().tolist()
    if not codes:
        return []
    with engine.begin() as cx:
        df = pd.read_sql(
            text("select id as cross_instance_id, cross_run_code from public.cross_instances where cross_run_code = any(:codes)"),
            cx, params={"codes": codes}
        )
    if df.empty:
        return []
    merged = rows.merge(df, on="cross_run_code", how="left")
    xids = merged["cross_instance_id"].dropna().astype(str).tolist()
    return [x for x in xids if uuid_re.match(x)]

safe_xids = _resolve_cross_instance_ids(eng, checked)
if not safe_xids:
    st.info("Select one or more rows; I’ll resolve their cross instances automatically.")
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

    if not sel_rows.empty:
        meta = realized[["clutch_code","cross_run_code","birthday"]].drop_duplicates()
        # map cross_instance_id back via cross_run_code
        with eng.begin() as cx:
            xir = pd.read_sql(
                text("select id as cross_instance_id, cross_run_code from public.cross_instances where id = any(:ids)"),
                cx, params={"ids": safe_xids}
            )
        table = sel_rows.merge(xir, on="cross_instance_id", how="left").merge(meta, on="cross_run_code", how="left")
        show_cols = [
            "clutch_code","cross_run_code","birthday",
            "selection_created_at","selection_annotated_at",
            "red_intensity","green_intensity","notes","annotated_by","label","selection_id",
        ]
        present = [c for c in show_cols if c in table.columns]
        st.dataframe(table[present], hide_index=True, use_container_width=True)
    else:
        st.info("No prior selection rows for the checked run(s).")

st.markdown("#### Quick annotate selected")
c1, c2, c3 = st.columns([1,1,3])
with c1:
    red_txt = st.text_input("red", value="", placeholder="text")
with c2:
    green_txt = st.text_input("green", value="", placeholder="text")
with c3:
    note_txt = st.text_input("note", value="", placeholder="optional")

if st.button("Submit"):
    if checked.empty:
        st.warning("No rows selected.")
    else:
        xids = _resolve_cross_instance_ids(eng, checked)
        if not xids:
            st.error("Couldn’t resolve any cross_instance_id from the selected rows.")
        else:
            saved = 0
            with eng.begin() as cx:
                for xid in xids:
                    base_label = " / ".join(
                        s for s in {
                            checked.get("clutch_code", pd.Series([""])).iloc[0] if "clutch_code" in checked.columns else "",
                            checked.get("cross_run_code", pd.Series([""])).iloc[0] if "cross_run_code" in checked.columns else "",
                        } if s
                    ) or "clutch"
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
# Reuse the last resolved IDs if available; otherwise show nothing.
if safe_xids:
    values_all = ", ".join([f"(uuid '{x}')" for x in safe_xids])
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
    if not table_all.empty:
        with eng.begin() as cx:
            xir = pd.read_sql(
                text("select id as cross_instance_id, cross_run_code from public.cross_instances where id = any(:ids)"),
                cx, params={"ids": safe_xids}
            )
        meta = realized[["clutch_code","cross_run_code","birthday"]].drop_duplicates()
        out = table_all.merge(xir, on="cross_instance_id", how="left").merge(meta, on="cross_run_code", how="left")
        cols = [
            "clutch_code","cross_run_code","birthday",
            "selection_created_at","selection_annotated_at",
            "red_intensity","green_intensity","notes","annotated_by","label","selection_id",
        ]
        present = [c for c in cols if c in out.columns]
        st.dataframe(out[present], hide_index=True, use_container_width=True)
else:
    st.caption("Select rows above to see their existing selection instances here.")