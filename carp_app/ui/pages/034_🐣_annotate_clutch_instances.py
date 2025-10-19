from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
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

st.set_page_config(page_title="Annotate Clutch Instances", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Clutch Instances")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

PAGE_SIZE = 50  # rows per "Load more" page

# ───────────────────────── helpers ─────────────────────────
def _view_exists(schema: str, name: str) -> bool:
    with eng.begin() as cx:
        q = text("select 1 from information_schema.views where table_schema=:s and table_name=:t limit 1")
        return bool(pd.read_sql(q, cx, params={"s": schema, "t": name}).shape[0])

def _safe_date(v):
    try:
        return pd.to_datetime(v).date() if pd.notna(v) else None
    except Exception:
        return None

def _load_instances(d1, d2, created_by, q, ignore_dates) -> pd.DataFrame:
    if not _view_exists("public","v_clutches_overview_final"):
        st.error("View public.v_clutches_overview_final not found."); st.stop()

    where_bits, params = [], {}
    if not ignore_dates:
        where_bits.append("coalesce(clutch_birthday, date_planned) between :d1 and :d2")
        params["d1"], params["d2"] = d1, d2
    if (created_by or "").strip():
        where_bits.append("(created_by_instance ilike :byl or created_by_plan ilike :byl)")
        params["byl"] = f"%{created_by.strip()}%"
    if (q or "").strip():
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
          coalesce(clutch_strain,'') ilike :ql or
          coalesce(treatments_pretty,'') ilike :ql
        )""")
        params["ql"] = f"%{q.strip()}%"
    where_sql = " AND ".join(where_bits) if where_bits else "true"

    sql = text(f"""
      select *
      from public.v_clutches_overview_final
      where {where_sql}
      order by created_at_instance desc nulls last, clutch_birthday desc nulls last
      limit 500
    """)
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params=params)

def _resolve_prefill_to_clutch_id(prefill_run: Optional[str], prefill_xid: Optional[str]) -> Optional[str]:
    """
    Resolve to clutch_id using run_code or cross_instance UUID.
    """
    if not (prefill_run or prefill_xid): return None
    cond, params = "", {}
    if prefill_xid:
        cond = "ci.id = cast(:xid as uuid)"; params["xid"] = prefill_xid
    else:
        cond = "ci.cross_run_code = :rc";    params["rc"]  = prefill_run
    sql = text(f"""
      select cl.id::text as clutch_id, ci.cross_run_code
      from public.cross_instances ci
      join public.clutches cl on cl.cross_instance_id = ci.id
      where {cond}
      limit 1
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return (df["clutch_id"].iloc[0] if not df.empty else None)

def _resolve_cross_instance_ids_by_clutch_ids(clutch_ids: List[str]) -> List[str]:
    """Return cross_instance_id list for a list of clutch UUIDs (as strings)."""
    if not clutch_ids:
        return []
    sql = text("""
      select cl.cross_instance_id::text as cross_instance_id
      from public.clutches cl
      where cl.id::text = any(:ids)              -- ← cast column to text
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": clutch_ids})
    return df["cross_instance_id"].dropna().astype(str).tolist() if not df.empty else []

# ───────────────────────── Filters (like Treatments page) ─────────────────────────
with st.form("filters", clear_on_submit=False):
    today = pd.Timestamp.today().date()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - pd.Timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + pd.Timedelta(days=14))
    with c3: created_by = st.text_input("Created by (plan/instance)", value="")
    with c4: q = st.text_input("Search (code/cross/clutch/genotype/strain)", value="")
    r1, r2 = st.columns([1,3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", use_container_width=True)

# ───────────────────────── Load instances grid (top) ─────────────────────────
instances = _load_instances(d1, d2, created_by, q, ignore_dates)
st.caption(f"{len(instances)} clutch instance(s)")

if instances.empty:
    st.info("No clutches found with the current filters."); st.stop()

# Auto-select from prefill if present
prefill_run  = st.session_state.pop("annotate_prefill_run", None)
prefill_xid  = st.session_state.pop("annotate_prefill_xid", None)
prefill_cid  = _resolve_prefill_to_clutch_id(prefill_run, prefill_xid)

grid = instances.copy()
if "✓ Select" not in grid.columns:
    grid.insert(0,"✓ Select", False)
if prefill_cid and "clutch_id" in grid.columns:
    grid.loc[grid["clutch_id"].astype(str).eq(prefill_cid), "✓ Select"] = True

view_cols = [
    "✓ Select",
    "clutch_code","clutch_birthday","cross_name_pretty",
    "genotype_treatment_rollup",                # rollup first (like treatments page)
    "clutch_genotype_pretty","clutch_genotype_canonical",
    "mom_strain","dad_strain","clutch_strain_pretty",
    "treatments_count","treatments_pretty",
    "created_by_instance","created_at_instance",
]
present = [c for c in view_cols if c in grid.columns]

edited = st.data_editor(
    grid[present], hide_index=True, use_container_width=True, num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True),
        "created_at_instance": st.column_config.DatetimeColumn("created_at_instance", disabled=True),
        "genotype_treatment_rollup": st.column_config.TextColumn(
            "genotype_treatment_rollup",
            help="Formatted as: treatments_pretty > clutch_genotype_pretty"
        ),
        "treatments_count":  st.column_config.NumberColumn("treatments_count", help="How many materials are attached"),
        "treatments_pretty": st.column_config.TextColumn("treatments_pretty", help="Codes of attached materials"),
    },
    key="annotate_instances_grid",
)

# Persist selection
grid.loc[edited.index, "✓ Select"] = edited["✓ Select"]
picked = grid.loc[grid["✓ Select"] == True].reset_index(drop=True)

st.markdown("### Realized instances (newest first)")
if picked.empty:
    st.info("Select one or more clutches above to enable annotation."); st.stop()

# Build a server-side subset of selected instances for the “runs” view if you want to see run codes
# (Optional – you can comment out this block if you prefer to annotate directly by clutch)
with eng.begin() as cx:
    df_runs = pd.read_sql(text("""
        select
            cl.id::text          as clutch_id,
            ci.id::text          as cross_instance_id,
            ci.cross_run_code,
            ci.cross_date
        from public.clutches cl
        join public.cross_instances ci on ci.id = cl.cross_instance_id
        where cl.id::text = any(:ids)               -- ← cast column to text
        order by ci.cross_date desc nulls last, ci.created_at desc nulls last
        """), cx, params={"ids": picked["clutch_id"].astype(str).tolist()})

if df_runs.empty:
    st.caption("No cross run rows found for the selected clutches (this is okay; you can still annotate).")
else:
    st.dataframe(df_runs[["clutch_id","cross_run_code","cross_date"]],
                 hide_index=True, use_container_width=True)

# ───────────────────────── Quick annotate selected ─────────────────────────
st.markdown("#### Quick annotate selected")
c1, c2, c3 = st.columns([1,1,3])
with c1: red_txt   = st.text_input("red",   value="", placeholder="text")
with c2: green_txt = st.text_input("green", value="", placeholder="text")
with c3: note_txt  = st.text_input("note",  value="", placeholder="optional")

def _resolve_cross_instance_ids_for_selected(df: pd.DataFrame) -> List[str]:
    if df.empty or "clutch_id" not in df.columns: return []
    return _resolve_cross_instance_ids_by_clutch_ids(df["clutch_id"].astype(str).tolist())

if st.button("Submit"):
    xids = _resolve_cross_instance_ids_for_selected(picked)
    if not xids:
        st.error("Couldn’t resolve any cross_instance_id from the selected rows.")
    else:
        saved = 0
        with eng.begin() as cx:
            for xid in xids:
                # derive a readable label from the selected instance code and (optional) run code
                lbl = ""
                if not df_runs.empty:
                    row = df_runs.loc[df_runs["cross_instance_id"] == xid]
                    if not row.empty:
                        lbl = f"{row.iloc[0]['cross_run_code']}"
                if not lbl:
                    # fallback to clutch_code visible in table
                    lbl = picked.get("clutch_code", pd.Series(["clutch"])).iloc[0] or "clutch"

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
                    "label": lbl,
                    "red":   red_txt,
                    "green": green_txt,
                    "note":  note_txt,
                    "fallback_user": (getattr(st, "experimental_user", None).email
                                      if hasattr(st, "experimental_user") and getattr(st.experimental_user, "email", None)
                                      else (getattr(user, "email", "") or "")),
                })
                saved += 1
        st.success(f"Created {saved} clutch instance(s).")
        st.rerun()

# ───────────────────────── Selection instances (distinct) ─────────────────────────
st.markdown("### Selection instances (distinct)")
xids = _resolve_cross_instance_ids_for_selected(picked)
if xids:
    values_all = ", ".join([f"(uuid '{x}')" for x in xids])
    sql_all = f"""
        with picked(id) as (values {values_all})
        select
          ci.id           as selection_id,
          ci.cross_instance_id,
          ci.clutch_instance_code,
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
        display_cols = [
            "clutch_instance_code",
            "selection_created_at","selection_annotated_at",
            "red_intensity","green_intensity","notes","annotated_by","label",
        ]
        present = [c for c in display_cols if c in table_all.columns]
        st.dataframe(table_all[present], hide_index=True, use_container_width=True)
else:
    st.caption("Select rows above to see their existing selection instances here.")