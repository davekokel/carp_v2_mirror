# =============================================================================
# 🧬 Select tank pairings (physical) — choose mother/father tanks and save
#     - Conceptual pair (unordered) is chosen first
#     - Step 1: select Mother tank from either fish
#     - Step 2: select Father tank from the other fish
#     - Step 3: save ONE tank_pairs row (role_orientation=0) using tanks(tank_id)
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from typing import List, Dict, Any, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine

# ── Auth + page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🧬 Select tank pairings", page_icon="🧬", layout="wide")
st.title("🧬 Select tank pairings")

# ── Engine ───────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine():
    return get_engine()

def _eng():
    if not os.getenv("DB_URL"):
        st.error("DB_URL not set"); st.stop()
    return _cached_engine()

with _eng().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# =============================================================================
# Helpers
# =============================================================================
@st.cache_data(show_spinner=False)
def _load_fish_pairs(q: str, limit: int = 200) -> pd.DataFrame:
    sql = text("""
      with pairs as (
        select
          fp.id::text                        as fish_pair_id,
          fp.fish_pair_code                  as fish_pair_code,
          mom.fish_code                      as parent1,
          dad.fish_code                      as parent2,
          fp.genotype_elems                  as genotype_elems,
          fp.created_by                      as created_by,
          fp.created_at                      as created_at
        from public.fish_pairs fp
        left join public.fish mom on mom.id = fp.mom_fish_id
        left join public.fish dad on dad.id = fp.dad_fish_id
      )
      select
        p.fish_pair_id,
        p.fish_pair_code,
        p.parent1,
        p.parent2,
        '' as clutch_code,
        case when p.genotype_elems is not null
             then array_to_string(p.genotype_elems, '; ')
             else '' end as clutch_genotype,
        p.created_by, p.created_at
      from pairs p
      where (
        :q = '' or
        p.fish_pair_code ilike :ql or
        p.parent1        ilike :ql or
        p.parent2        ilike :ql
      )
      order by p.created_at desc nulls last
      limit :lim
    """)
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params={"q": (q or ""), "ql": f"%{q or ''}%", "lim": int(limit)})

@st.cache_data(show_spinner=False)
def _load_live_tanks_for_fish(codes: List[str]) -> pd.DataFrame:
    """
    Live tanks for given fish_code list from v_tanks (status IN ('active','new')).
    Must include tanks.tank_id so we can satisfy FKs to public.tanks(tank_id).
    """
    if not codes:
        return pd.DataFrame()
    # ensure we always return tank_id + tank_code
    sql = text("""
        select
            vt.fish_code,
            vt.tank_code,
            vt.tank_uuid::text    as tank_id,
            coalesce(vt.status::text,'') as status,
            vt.created_at  as created_at
        from public.v_tanks vt
        where vt.fish_code = any(:codes)
          and vt.status::text = any(:live)
        order by vt.fish_code, vt.created_at desc nulls last
    """)
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": list({c for c in codes if c}), "live": ["active","new"]})

def _ensure_fish_pair(a_code: str, b_code: str, created_by_val: str) -> str:
    """
    Ensure fish_pairs row exists (unordered -> ordered by code).
    Returns fish_pairs.id (UUID as string).
    """
    with _eng().begin() as cx:
        got = cx.execute(text("""
          with canon as (
            select least(:a,:b) as a, greatest(:a,:b) as b
          ),
          ids as (
            select
              (select id from public.fish where fish_code = (select a from canon) limit 1) as mom_id,
              (select id from public.fish where fish_code = (select b from canon) limit 1) as dad_id
          ),
          existing as (
            select id from public.fish_pairs
            where mom_fish_id = (select mom_id from ids)
              and dad_fish_id = (select dad_id from ids)
          ),
          up as (
            update public.fish_pairs
               set created_by = coalesce(:by, created_by),
                   created_at = now()
             where id in (select id from existing)
            returning id
          ),
          ins as (
            insert into public.fish_pairs
              (fish_pair_code, mom_fish_id, dad_fish_id, genotype_elems, created_by)
            select
              'FP-'||to_char(extract(year from now())::int % 100,'FM00')||
              lpad((
                select coalesce(max((regexp_match(coalesce(fish_pair_code,''),
                     '^FP-\\d{2}(\\d{4})$'))[1]::int),0) + 1
                from public.fish_pairs
                where fish_pair_code like 'FP-'||to_char(extract(year from now())::int % 100,'FM00')||'%'
              )::text, 4, '0') as fish_pair_code,
              ids.mom_id,
              ids.dad_id,
              null,
              :by
            from ids
            where not exists (select 1 from existing)
            returning id
          )
          select coalesce((select id from up), (select id from ins))::text as id;
        """), {"a": a_code, "b": b_code, "by": created_by_val}).mappings().first()
        return str(got["id"])

def _find_existing_tank_pair(mother_id: str, father_id: str) -> str | None:
    with _eng().begin() as cx:
        df = pd.read_sql(
            text("""
              select id::text
              from public.tank_pairs
              where mother_tank_id = cast(:mom as uuid)
                and father_tank_id = cast(:dad as uuid)
                and concept_id is null
              limit 1
            """),
            cx, params={"mom": mother_id, "dad": father_id}
        )
    return (df["id"].iloc[0] if not df.empty else None)

def _upsert_one_pair(fish_pair_id: str, mother_tank_id: str, father_tank_id: str,
                     created_by_val: str, note: str) -> tuple[bool, str]:
    existing = _find_existing_tank_pair(mother_tank_id, father_tank_id)
    with _eng().begin() as cx:
        if existing:
            cx.execute(text("""
              update public.tank_pairs
                 set updated_at = now(),
                     note = coalesce(nullif(:note,''), note)
               where id = cast(:id as uuid)
            """), {"id": existing, "note": note})
            tp_code = cx.execute(
                text("select tank_pair_code from public.tank_pairs where id = cast(:id as uuid)"),
                {"id": existing}
            ).scalar() or existing
            return (False, tp_code)

        tp_code = cx.execute(text("""
          insert into public.tank_pairs
            (concept_id, fish_pair_id, mother_tank_id, father_tank_id, status, created_by, note)
          values
            (null, cast(:fp as uuid), cast(:mom as uuid), cast(:dad as uuid), 'selected', :by, nullif(:note,''))
          returning tank_pair_code
        """), {"fp": fish_pair_id, "mom": mother_tank_id, "dad": father_tank_id,
               "by": created_by_val, "note": note}).scalar() or ""
        return (True, tp_code)

# =============================================================================
# 0) Pick conceptual fish pair
# =============================================================================
st.markdown("### 0) Pick a fish pair (conceptual)")
cc1, cc2, cc3 = st.columns([3,1,1])
with cc1:
    q_pairs = st.text_input("Search (pair code / fish_code / clutch code)", value="")
with cc2:
    lim_pairs = int(st.number_input("Limit", min_value=10, max_value=2000, value=200, step=50))
with cc3:
    st.write("")
    if st.button("↻ Refresh", width="stretch"):
        st.cache_data.clear()

pairs_df = _load_fish_pairs(q_pairs, lim_pairs)
if pairs_df.empty:
    st.info("No conceptual fish pairs yet. Create them on **Select fish pairs**.")
    st.stop()

pairs_view = pairs_df.copy()
if "✓ Select" not in pairs_view.columns:
    pairs_view.insert(0, "✓ Select", False)

cols = ["✓ Select","fish_pair_code","parent1","parent2","clutch_code","clutch_genotype","created_at","created_by"]
for c in cols:
    if c not in pairs_view.columns:
        pairs_view[c] = ""
picked = st.data_editor(
    pairs_view[cols],
    hide_index=True, width="stretch",
    column_config={
        "✓ Select":        st.column_config.CheckboxColumn("✓", default=False),
        "fish_pair_code":  st.column_config.TextColumn("Fish pair", disabled=True),
        "parent1":         st.column_config.TextColumn("Parent A", disabled=True),
        "parent2":         st.column_config.TextColumn("Parent B", disabled=True),
        "clutch_code":     st.column_config.TextColumn("Clutch", disabled=True),
        "clutch_genotype": st.column_config.TextColumn("Clutch genotype", disabled=True),
        "created_at":      st.column_config.DatetimeColumn("Created", disabled=True),
        "created_by":      st.column_config.TextColumn("Created by", disabled=True),
    },
    key="fish_pairs_picker",
)
mask = picked.get("✓ Select", pd.Series(False, index=picked.index)).fillna(False).astype(bool)
chosen = pairs_view.loc[mask].head(1)
if chosen.empty:
    st.info("Select a fish pair above to continue.")
    st.stop()

row = chosen.iloc[0]
parent_a = str(row["parent1"])
parent_b = str(row["parent2"])
st.success(f"Selected {row['fish_pair_code']}: {parent_a} + {parent_b} (unordered).")

# =============================================================================
# 1) Select Mother tank (from either fish)
# =============================================================================
st.markdown("### 1) Select **Mother** tank")
mothers = _load_live_tanks_for_fish([parent_a, parent_b]).copy()
if mothers.empty:
    st.warning("No live tanks found for either parent.")
    st.stop()

mother_df = mothers.rename(columns={"fish_code":"FSH","tank_code":"tank"})
if "✓ Mother" not in mother_df.columns:
    mother_df.insert(0,"✓ Mother", False)
mother_edit = st.data_editor(
    mother_df[["✓ Mother","FSH","tank","tank_id","status","created_at"]],
    hide_index=True, width="stretch",
    column_config={
        "✓ Mother": st.column_config.CheckboxColumn("✓", default=False),
        "FSH":      st.column_config.TextColumn("Fish (candidate mother)", disabled=True),
        "tank":     st.column_config.TextColumn("Tank", disabled=True),
        "tank_id":  st.column_config.TextColumn("tank_id", disabled=True),
        "status":   st.column_config.TextColumn("Status", disabled=True),
        "created_at": st.column_config.DatetimeColumn("Created", disabled=True),
    },
    key="mother_picker",
)
mother_sel = mother_edit[mother_edit["✓ Mother"]]
if mother_sel.shape[0] == 0:
    st.info("Pick one mother tank above."); st.stop()
if mother_sel.shape[0] > 1:
    st.warning("Multiple mother tanks selected; using the first.")
mother_row = mother_sel.head(1).iloc[0]
mother_tank_id = str(mother_row["tank_id"])
mother_fsh     = str(mother_row["FSH"])

# =============================================================================
# 2) Select Father tank (from the other fish’s tanks)
# =============================================================================
st.markdown("### 2) Select **Father** tank")
other_fish = parent_b if mother_fsh == parent_a else parent_a
fathers = _load_live_tanks_for_fish([other_fish]).copy()
if fathers.empty:
    st.warning(f"No live tanks found for the other parent ({other_fish})."); st.stop()

father_df = fathers.rename(columns={"fish_code":"FSH","tank_code":"tank"})
if "✓ Father" not in father_df.columns:
    father_df.insert(0,"✓ Father", False)
father_edit = st.data_editor(
    father_df[["✓ Father","FSH","tank","tank_id","status","created_at"]],
    hide_index=True, width="stretch",
    column_config={
        "✓ Father": st.column_config.CheckboxColumn("✓", default=False),
        "FSH":      st.column_config.TextColumn("Fish (candidate father)", disabled=True),
        "tank":     st.column_config.TextColumn("Tank", disabled=True),
        "tank_id":  st.column_config.TextColumn("tank_id", disabled=True),
        "status":   st.column_config.TextColumn("Status", disabled=True),
        "created_at": st.column_config.DatetimeColumn("Created", disabled=True),
    },
    key="father_picker",
)
father_sel = father_edit[father_edit["✓ Father"]]
if father_sel.shape[0] == 0:
    st.info("Pick one father tank above."); st.stop()
if father_sel.shape[0] > 1:
    st.warning("Multiple father tanks selected; using the first.")
father_row = father_sel.head(1).iloc[0]
father_tank_id = str(father_row["tank_id"])
father_fsh     = str(father_row["FSH"])

if mother_tank_id == father_tank_id:
    st.error("Mother and Father cannot be the same tank."); st.stop()

# =============================================================================
# 3) Save tank_pair (mother/father)
# =============================================================================
st.markdown("### 3) Save tank_pair parents")
cs1, cs2 = st.columns([1,2])
with cs1:
    created_by_val = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown")
    note_val = st.text_input("Note (optional)", value="")
    can_save = bool(mother_tank_id and father_tank_id)

    if st.button("💾 Save mother/father pairing", type="primary", width="stretch", disabled=not can_save):
        fp_id = _ensure_fish_pair(parent_a, parent_b, created_by_val)
        inserted, tp_code = _upsert_one_pair(fp_id, mother_tank_id, father_tank_id, created_by_val, note_val)
        if inserted:
            st.success(f"Saved tank_pair {tp_code} (mother={mother_fsh}, father={father_fsh}).")
        else:
            st.success(f"Updated tank_pair {tp_code} (mother={mother_fsh}, father={father_fsh}).")
        st.cache_data.clear()

with cs2:
    st.markdown("**Recent tank_pairs for these tanks**")
    sql_recent = text("""
      select
        tp.tank_pair_code,
        tp.status,
        tm.fish_code                                as mom_fish_code,
        tm.tank_code                                as mom_tank_code,
        coalesce(vm.transgene_pretty_name, '')      as mom_genotype,
        tf.fish_code                                as dad_fish_code,
        tf.tank_code                                as dad_tank_code,
        coalesce(vf.transgene_pretty_name, '')      as dad_genotype,
        tp.note,
        tp.created_by,
        tp.created_at
      from public.tank_pairs tp
      left join public.tanks tm on tm.tank_uuid = tp.mother_tank_id
      left join public.tanks tf on tf.tank_uuid = tp.father_tank_id
      left join public.v_fish_richoverview_rich vm on vm.fish_code = tm.fish_code
      left join public.v_fish_richoverview_rich vf on vf.fish_code = tf.fish_code
      where tp.mother_tank_id = cast(:mom as uuid)
         or tp.father_tank_id = cast(:dad as uuid)
      order by tp.created_at desc nulls last
      limit 50
    """)
    with _eng().begin() as cx:
        recent = pd.read_sql(sql_recent, cx, params={"mom": mother_tank_id, "dad": father_tank_id})

    if recent.empty:
        st.info("No tank_pairs yet for this selection.")
    else:
        cols = [
            "tank_pair_code", "status",
            "mom_fish_code", "mom_tank_code", "mom_genotype",
            "dad_fish_code", "dad_tank_code", "dad_genotype",
            "note", "created_by", "created_at",
        ]
        st.dataframe(recent[cols], width="stretch", hide_index=True)