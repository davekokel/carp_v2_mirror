from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()
from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="🐣 Annotate Clutch Instances", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Clutch Instances")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

def _exists(full: str) -> bool:
    sch, tab = full.split(".", 1)
    q = text("""
      with t as (
        select table_schema as s, table_name as t from information_schema.tables
        union all
        select table_schema as s, table_name as t from information_schema.views
      )
      select exists(select 1 from t where s=:s and t=:t) as ok
    """)
    with eng.begin() as cx:
        return bool(pd.read_sql(q, cx, params={"s": sch, "t": tab})["ok"].iloc[0])

def _load_clutches_filtered(d1: date, d2: date, created_by: str, qtxt: str, ignore_dates: bool) -> pd.DataFrame:
    view = "public.v_clutches_overview_effective"
    if not _exists(view):
        st.error(f"Required view {view} not found."); st.stop()

    where_bits, params = [], {}
    if not ignore_dates:
        where_bits.append("coalesce(clutch_birthday, date_planned) between :d1 and :d2")
        params["d1"], params["d2"] = d1, d2
    if (created_by or "").strip():
        where_bits.append("(created_by_instance ilike :byl or created_by_plan ilike :byl)")
        params["byl"] = f"%{created_by.strip()}%"
    if (qtxt or "").strip():
        where_bits.append("""(
          coalesce(clutch_code,'') ilike :ql or
          coalesce(cross_name_pretty,'') ilike :ql or
          coalesce(cross_name,'') ilike :ql or
          coalesce(clutch_name,'') ilike :ql or
          coalesce(clutch_nickname,'') ilike :ql or
          coalesce(clutch_genotype_pretty,'') ilike :ql or
          coalesce(clutch_genotype_canonical,'') ilike :ql or
          coalesce(mom_strain,'') ilike :ql or
          coalesce(dad_strain,'') ilike :ql or
          coalesce(clutch_strain,'') ilike :ql
        )""")
        params["ql"] = f"%{qtxt.strip()}%"
    where_sql = " AND ".join(where_bits) if where_bits else "true"

    sql = text(f"""
      select b.*
      from {view} b
      where {where_sql}
      order by created_at_instance desc nulls last, clutch_birthday desc nulls last
      limit 500
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    if "treatments_count_effective_eff" in df.columns:
        df["treatments_count_effective"] = df["treatments_count_effective_eff"]
    if "treatments_pretty_effective_eff" in df.columns:
        df["treatments_pretty_effective"] = df["treatments_pretty_effective_eff"]
    if "genotype_treatment_rollup_effective_eff" in df.columns:
        df["genotype_treatment_rollup_effective"] = df["genotype_treatment_rollup_effective_eff"]

    if "treatments_count_effective" in df.columns:
        df["treatments_count_effective"] = pd.to_numeric(df["treatments_count_effective"], errors="coerce").fillna(0).astype(int)

    if "clutch_code" not in df.columns:
        df["clutch_code"] = ""

    df = df.loc[:, ~df.columns.duplicated()]
    return df

def _resolve_ci_id(ci_code: str) -> Optional[str]:
    if not ci_code or not isinstance(ci_code, str):
        return None
    with eng.begin() as cx:
        df = pd.read_sql(text("""
            select id::text as clutch_instance_id
            from public.clutch_instances
            where clutch_instance_code = :ci
            limit 1
        """), cx, params={"ci": ci_code})
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
        df = pd.read_sql(text("""
            select id::text as clutch_instance_id
            from public.clutch_instances
            where upper(regexp_replace(coalesce(clutch_instance_code,''), '-[0-9]{2}$','')) =
                  upper(regexp_replace(:ci, '^CI-',''))
            limit 1
        """), cx, params={"ci": ci_code})
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
        df = pd.read_sql(text("""
            select ci.id::text as clutch_instance_id
            from public.clutch_instances ci
            join public.cross_instances x on x.id = ci.cross_instance_id
            where upper(regexp_replace(x.cross_run_code, '-[0-9]{2}$','')) =
                  upper(regexp_replace(:ci, '^CI-',''))
            order by ci.created_at desc nulls last
            limit 1
        """), cx, params={"ci": ci_code})
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
    return None

def _load_ci_annotation(cid: str) -> pd.DataFrame:
    sql = text("""
      select
        id::text                    as clutch_instance_id,
        clutch_instance_code,
        label,
        red_intensity,
        green_intensity,
        notes,
        red_selected,
        green_selected,
        annotated_by,
        annotated_at,
        created_at
      from public.clutch_instances
      where id = cast(:cid as uuid)
      limit 1
    """)
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params={"cid": cid})

def _update_ci_annotation(cid: str, red: str, green: str, note: str, fallback_user: str):
    sql = text("""
      update public.clutch_instances
      set
        red_intensity   = nullif(:red,''),
        green_intensity = nullif(:green,''),
        notes           = nullif(:note,''),
        red_selected    = case when nullif(:red,'')   is not null then true else false end,
        green_selected  = case when nullif(:green,'') is not null then true else false end,
        annotated_by    = coalesce(current_setting('app.user', true), :fallback_user),
        annotated_at    = now()
      where id = cast(:cid as uuid)
    """)
    with eng.begin() as cx:
        cx.execute(sql, {
            "cid": cid,
            "red": red,
            "green": green,
            "note": note,
            "fallback_user": (getattr(user, "email", "") or fallback_user or ""),
        })

with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: created_by = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt = st.text_input("Search (code/cross/clutch/genotype/strain)", value="")
    r1, r2 = st.columns([1,3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", use_container_width=True)

clutches = _load_clutches_filtered(d1, d2, created_by, qtxt, ignore_dates)
st.caption(f"{len(clutches)} clutch(es)")

if clutches.empty:
    st.info("No clutches found with the current filters."); st.stop()

view_cols = [
    "clutch_code",
    "cross_name_pretty",
    "clutch_name",
    "clutch_genotype_pretty",
    "genotype_treatment_rollup_effective",
    "treatments_count_effective",
    "treatments_pretty_effective",
    "clutch_birthday",
    "created_by_instance",
]
have = [c for c in view_cols if c in clutches.columns]
dfv = clutches[have].copy()
dfv = dfv.loc[:, ~dfv.columns.duplicated()]
if "treatments_count_effective" in dfv.columns:
    dfv["treatments_count_effective"] = pd.to_numeric(dfv["treatments_count_effective"], errors="coerce").fillna(0).astype(int)

last_ci = st.session_state.get("__annot_last_ci")
dfv.insert(0, "✓ Select", False)
if last_ci and "clutch_code" in dfv.columns:
    dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True),
    },
    key="annotate_ci_picker_v1",
)

sel_mask = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False).astype(bool)
picked = dfv.loc[sel_mask, :].reset_index(drop=True)

if picked.empty:
    st.info("Select a **CI-…** row to annotate it directly.")
    st.stop()

ci_code = str(picked.iloc[0].get("clutch_code","")).strip()
st.session_state["__annot_last_ci"] = ci_code

if not ci_code.startswith("CI-"):
    st.warning("Pick a **CI-…** row (runs only). Plan rows (CL-…) can’t be annotated here."); st.stop()

cid = _resolve_ci_id(ci_code)
if not cid:
    st.error("Could not resolve clutch_instance_id from this CI code."); st.stop()

st.subheader("Annotate this clutch instance")
current = _load_ci_annotation(cid)
cur = current.iloc[0] if not current.empty else {}

c1, c2, c3 = st.columns([1,1,2])
with c1:
    red_txt = st.text_input("red",  value=str(cur.get("red_intensity") or ""), placeholder="text")
with c2:
    green_txt = st.text_input("green", value=str(cur.get("green_intensity") or ""), placeholder="text")
with c3:
    note_txt = st.text_input("note", value=str(cur.get("notes") or ""), placeholder="optional")

save_col, = st.columns([1])
with save_col:
    if st.button("Save annotation", use_container_width=True, key="save_ci_annotation"):
        _update_ci_annotation(cid, red_txt, green_txt, note_txt, fallback_user=(getattr(user, "email", "") or ""))
        st.success("Annotation saved.")

st.subheader("Updated clutch instance")
updated = _load_ci_annotation(cid)
if updated.empty:
    st.info("No record found (unexpected).")
else:
    show_cols = [
        "clutch_instance_code","label","red_intensity","green_intensity","notes",
        "red_selected","green_selected","annotated_by","annotated_at","created_at"
    ]
    present = [c for c in show_cols if c in updated.columns]
    st.dataframe(updated[present], use_container_width=True, hide_index=True)