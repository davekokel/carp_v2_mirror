from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date
from typing import Optional, List

import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp

# ── Auth ─────────────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🗓 Schedule new cross", page_icon="🗓", layout="wide")
st.title("🗓 Schedule new cross")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

VIEW_CLUTCHES = "v_clutches"       # canonical clutch concepts
VIEW_TANK_PAIRS = "v_tank_pairs"   # friendly tank-pair details
TABLE_TANK_PAIRS = "tank_pairs"    # mother_tank_id / father_tank_id source
TABLE_CLUTCH_PLANS = "clutch_plans"
TABLE_CROSS_INSTANCES = "cross_instances"

# ── Helpers ──────────────────────────────────────────────────────────────────
def _safe_df(cx, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
    try:
        return pd.read_sql(text(sql), cx, params=params or {})
    except Exception as e:
        st.error(f"Query failed: {e}")
        return pd.DataFrame()

def _get_schema_columns(cx, schema: str, name: str) -> list[str]:
    df = pd.read_sql(
        text("""select column_name
                from information_schema.columns
                where table_schema=:s and table_name=:t
                order by ordinal_position"""),
        cx, params={"s": schema, "t": name}
    )
    return df["column_name"].tolist()

def _table_has_columns(cx, schema: str, name: str, *cols: str) -> bool:
    have = set(_get_schema_columns(cx, schema, name))
    return all(c in have for c in cols)

# ── Filters for concepts (clutches to produce) ───────────────────────────────
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    q = c1.text_input("Search (code/name/nickname/FSH)")
    d_from = c2.date_input("From", value=None)
    d_to   = c3.date_input("To", value=None)
    created_by = c4.text_input("Created by")
    most_recent = st.toggle("Most recent (ignore dates)", value=True)
    _ = st.form_submit_button("Apply")

where, params = [], {}
if not most_recent:
    if d_from: where.append("c.created_at >= :d1"); params["d1"] = str(d_from)
    if d_to:   where.append("c.created_at <= :d2"); params["d2"] = str(d_to)
if created_by:
    where.append("c.created_by ilike :cb"); params["cb"] = f"%{created_by}%"
if q:
    params["q"] = f"%{q.strip()}%"
    where.append("""(
      c.clutch_code ilike :q or c.name ilike :q or c.nickname ilike :q or
      c.mom_code ilike :q or c.dad_code ilike :q
    )""")
where_sql = (" where " + " AND ".join(where)) if where else ""

# ── Step 1: Select the clutch concept(s) you want to generate ────────────────
with eng.begin() as cx:
    df_concepts = _safe_df(cx, f"""
      select c.*
      from public.{VIEW_CLUTCHES} c
      {where_sql}
      order by c.created_at desc nulls last
      limit 500
    """, params)
st.subheader("1) Select the clutch genotype you want to generate")
if df_concepts.empty:
    st.info("No clutch concepts match."); st.stop()

concept_vis = df_concepts.copy()
sel_key = "clutch_code" if "clutch_code" in concept_vis.columns else concept_vis.columns[0]
concept_vis.insert(0, "✓ Select", False)
concept_pick = st.data_editor(
    concept_vis,
    hide_index=True, use_container_width=True,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
    key="concept_editor",
)
mask_concept = concept_pick.get("✓ Select", pd.Series(False, index=concept_pick.index)).astype(bool)
selected_concepts: List[str] = concept_pick.loc[mask_concept, sel_key].astype(str).tolist()

# Guard: require one concept (we’ll keep it simple)
if not selected_concepts:
    st.warning("Pick one clutch concept above, then scroll down."); st.stop()
concept_code = selected_concepts[0]

# ── Step 2: Show schedule candidates (saved tank_pairs for this concept) ─────
st.subheader("2) Schedule candidates (saved tank_pairs for this concept)")
with eng.begin() as cx:
    # Resolve the clutch_plan row by code
    cp = _safe_df(cx, f"""
      select id as clutch_plan_id, clutch_code, created_by, created_at,
             tank_pair_id
      from public.{TABLE_CLUTCH_PLANS}
      where clutch_code = :code
      limit 1
    """, {"code": concept_code})

    if cp.empty:
        st.error(f"No clutch_plan found for {concept_code}."); st.stop()

    clutch_plan_id = cp["clutch_plan_id"].iloc[0]
    tank_pair_id = cp["tank_pair_id"].iloc[0] if "tank_pair_id" in cp.columns else None

    # If we have a saved tank_pair for this concept, show it; else show all pairs for manual choice
    if pd.notna(tank_pair_id):
        df_pairs = _safe_df(cx, f"""
          select
            tp.id as tank_pair_id,
            tp.tank_pair_code,
            vtp.mom_fish_code as mom_fish_code,
            vtp.mom_tank_code as mom_tank_code,
            vtp.dad_fish_code as dad_fish_code,
            vtp.dad_tank_code as dad_tank_code,
            tp.mother_tank_id, tp.father_tank_id,
            :code as clutch_code,
            'selected'::text as status
          from public.{TABLE_TANK_PAIRS} tp
          left join public.{VIEW_TANK_PAIRS} vtp
            on vtp.mother_tank_id = tp.mother_tank_id
           and vtp.father_tank_id = tp.father_tank_id
          where tp.id = :tpid
        """, {"tpid": tank_pair_id, "code": concept_code})
    else:
        df_pairs = _safe_df(cx, f"""
          select
            tp.id as tank_pair_id,
            tp.tank_pair_code,
            vtp.mom_fish_code as mom_fish_code,
            vtp.mom_tank_code as mom_tank_code,
            vtp.dad_fish_code as dad_fish_code,
            vtp.dad_tank_code as dad_tank_code,
            tp.mother_tank_id, tp.father_tank_id,
            null::text as clutch_code,
            'candidate'::text as status
          from public.{TABLE_TANK_PAIRS} tp
          left join public.{VIEW_TANK_PAIRS} vtp
            on vtp.mother_tank_id = tp.mother_tank_id
           and vtp.father_tank_id = tp.father_tank_id
          order by tp.created_at desc nulls last
          limit 200
        """)

if df_pairs.empty:
    st.info("No saved tank_pairs for this concept. Use “select tank pairs” first, or pick from all pairs above.")
else:
    pairs_vis = df_pairs.copy()
    if "tank_pair_id" not in pairs_vis.columns:
        st.error("Expected column tank_pair_id missing."); st.stop()
    pairs_vis.insert(0, "✓ Select", False)
    pairs_pick = st.data_editor(
        pairs_vis,
        hide_index=True, use_container_width=True,
        column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
        key="pairs_editor",
    )
    mask_pairs = pairs_pick.get("✓ Select", pd.Series(False, index=pairs_pick.index)).astype(bool)
    selected_pair_ids: List[str] = pairs_pick.loc[mask_pairs, "tank_pair_id"].astype(str).tolist()

# ── Step 3: Reschedule selected tank_pair(s) → new cross instance(s) ─────────
st.subheader("3) Reschedule selected tank_pair(s) → new cross instance(s)")
c1, c2 = st.columns([1, 3])
run_date: date = c1.date_input("Run date", value=date.today())
note = c2.text_input("Note (optional)")

btn = st.button("⏱ Schedule selected tank_pair(s)", type="primary", use_container_width=True)

def _schedule_pairs(pairs: list[str], run_date: date, created_by: str, note: str) -> tuple[int, list[str], list[str]]:
    if not pairs:
        return 0, [], ["No tank pairs selected."]
    ok, skipped, errors = 0, [], []
    with eng.begin() as cx:
        # detect schema support for tank_pair_id on cross_instances
        has_tpid = False
        try:
            has_tpid = pd.read_sql(
                text("""
                  select 1
                  from information_schema.columns
                  where table_schema='public' and table_name='cross_instances' and column_name='tank_pair_id'
                  limit 1
                """),
                cx
            ).shape[0] == 1
        except Exception:
            has_tpid = False

        for pid in pairs:
            try:
                if has_tpid:
                    # Insert using tank_pair_id with NOT EXISTS guard (no ON CONFLICT)
                    row = pd.read_sql(
                        text("""
                          with tp as (
                            select id, mother_tank_id, father_tank_id
                            from public.tank_pairs
                            where id = cast(:pid as uuid)
                            limit 1
                          )
                          insert into public.cross_instances (tank_pair_id, cross_date, note, created_by)
                          select tp.id, :d, nullif(:note,'')::text, :by
                          from tp
                          where not exists (
                            select 1 from public.cross_instances ci
                            where ci.tank_pair_id = tp.id
                              and ci.cross_date   = :d
                          )
                          returning id
                        """),
                        cx, params={"pid": pid, "d": str(run_date), "by": created_by, "note": note}
                    )
                else:
                    # Fallback: insert using mother/father tank ids with NOT EXISTS guard
                    row = pd.read_sql(
                        text("""
                          with tp as (
                            select mother_tank_id, father_tank_id
                            from public.tank_pairs
                            where id = cast(:pid as uuid)
                            limit 1
                          )
                          insert into public.cross_instances (mother_tank_id, father_tank_id, cross_date, note, created_by)
                          select tp.mother_tank_id, tp.father_tank_id, :d, nullif(:note,'')::text, :by
                          from tp
                          where not exists (
                            select 1 from public.cross_instances ci
                            where ci.mother_tank_id = tp.mother_tank_id
                              and ci.father_tank_id = tp.father_tank_id
                              and ci.cross_date     = :d
                          )
                          returning id
                        """),
                        cx, params={"pid": pid, "d": str(run_date), "by": created_by, "note": note}
                    )

                if row.empty:
                    skipped.append(pid)  # already scheduled for this date
                else:
                    ok += 1
            except Exception as e:
                errors.append(f"{pid}: {e}")
    return ok, skipped, errors

if btn:
    n_ok, skipped, errs = _schedule_pairs(selected_pair_ids, run_date, user.get('email') or user.get('id') or "unknown", note)
    if n_ok:
        st.success(f"Saved {n_ok} cross_instance row(s).")
    if skipped:
        st.warning(f"Skipped {len(skipped)} (already scheduled for {run_date}).")
    if errs:
        st.error("Errors:\n" + "\n".join(errs))

# ── After-action: quick preview of what exists now ───────────────────────────
with eng.begin() as cx:
    preview = _safe_df(cx, """
      select *
      from public.v_crosses
      order by created_at desc nulls last
      limit 20
    """)
if not preview.empty:
    st.caption("Recent crosses (from v_crosses)")
    st.dataframe(preview, use_container_width=True, hide_index=True)