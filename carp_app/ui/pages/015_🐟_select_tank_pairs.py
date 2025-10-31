# =============================================================================
# 🧬 Select tank pairings (physical) — choose mother/father tanks and save
#     - Parents are chosen on this page
#     - Step 1: select Mother tank from either parent
#     - Step 2: select Father tank from the other parent
#     - Step 3: save ONE tank_pairs row (by tank_uuid)
#     - Step 4: create a cross_instance (trigger derives run code)
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date as _date
from typing import List

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
def _table_cols(schema: str, table: str) -> list[str]:
    with _eng().begin() as cx:
        df = pd.read_sql(
            text("""select column_name
                    from information_schema.columns
                    where table_schema=:s and table_name=:t
                    order by ordinal_position"""),
            cx, params={"s": schema, "t": table}
        )
    return df["column_name"].tolist()

def _tankpair_parent_cols() -> tuple[str, str]:
    cols = set(_table_cols("public", "tank_pairs"))
    for a, b in (("mother_tank_id","father_tank_id"), ("tank_id_mother","tank_id_father")):
        if a in cols and b in cols:
            return a, b
    raise RuntimeError("public.tank_pairs lacks expected mother/father tank id columns")

@st.cache_data(show_spinner=False)
def _pick_fish_view() -> str:
    with _eng().begin() as cx:
        rows = pd.read_sql(
            text("""select table_name
                    from information_schema.views
                    where table_schema='public'
                      and table_name in ('v_fish_rich','v_fish')"""),
            cx
        )
    names = set(rows["table_name"].tolist())
    return "public.v_fish_rich" if "v_fish_rich" in names else "public.v_fish"

def _fish_genotype_col(view: str) -> str | None:
    schema, tbl = view.split(".", 1)
    with _eng().begin() as cx:
        df = pd.read_sql(
            text("""select column_name
                    from information_schema.columns
                    where table_schema=:s and table_name=:t"""),
            cx, params={"s": schema, "t": tbl}
        )
    cols = set(df["column_name"].tolist())
    for c in ("transgene_pretty_name", "genotype_rollup"):
        if c in cols:
            return c
    return None

@st.cache_data(show_spinner=False)
def _load_live_tanks_for_fish(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame()
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

def _find_existing_tank_pair(mother_id: str, father_id: str) -> str | None:
    mom_col, dad_col = _tankpair_parent_cols()
    with _eng().begin() as cx:
        df = pd.read_sql(
            text(f"""select id::text
                     from public.tank_pairs
                     where {mom_col} = cast(:mom as uuid)
                       and {dad_col} = cast(:dad as uuid)
                       and concept_id is null
                     limit 1"""),
            cx, params={"mom": mother_id, "dad": father_id}
        )
    return (df["id"].iloc[0] if not df.empty else None)

def _upsert_one_pair(mother_tank_id: str, father_tank_id: str,
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
            (mother_tank_id, father_tank_id, status, created_by, note)
          values
            (cast(:mom as uuid), cast(:dad as uuid), 'selected', :by, nullif(:note,''))
          returning tank_pair_code
        """), {"mom": mother_tank_id, "dad": father_tank_id,
               "by": created_by_val, "note": note}).scalar() or ""
        return (True, tp_code)

# =============================================================================
# 0) Pick a conceptual pair (unordered) — computed (no fish_pairs table)
# =============================================================================
st.subheader("Pick a conceptual pair (unordered)")

@st.cache_data(show_spinner=False)
def _conceptual_pairs_chunk(off: int, lim: int, q: str = "") -> pd.DataFrame:
    sql = text("""
      with recent_tp as (
        select tp.tank_pair_code, max(ci.cross_date) as last_cross_date
        from public.tank_pairs tp
        left join public.cross_instances ci on ci.tank_pair_code = tp.tank_pair_code
        group by tp.tank_pair_code
      ),
      tp_fish as (
        select tp.tank_pair_code,
               vtm.fish_code as mom_fish,
               vtf.fish_code as dad_fish
        from public.tank_pairs tp
        left join public.v_tanks vtm on vtm.tank_uuid = tp.mother_tank_id
        left join public.v_tanks vtf on vtf.tank_uuid = tp.father_tank_id
      ),
      recent_pairs as (
        select least(mom_fish, dad_fish) as a,
               greatest(mom_fish, dad_fish) as b,
               max(r.last_cross_date) as last_cross
        from tp_fish tpf
        join recent_tp r using (tank_pair_code)
        where mom_fish is not null and dad_fish is not null
        group by 1,2
      ),
      live_pairs as (
        select least(m.fish_code, d.fish_code) as a,
               greatest(m.fish_code, d.fish_code) as b,
               null::date as last_cross
        from public.v_tanks m
        join public.v_tanks d on d.fish_code <> m.fish_code
        where m.status::text in ('active','new') and d.status::text in ('active','new')
      ),
      unioned as (
        select a,b,last_cross from recent_pairs
        union
        select a,b,last_cross from live_pairs
      )
      select a as parent_a, b as parent_b, max(last_cross) as last_cross
      from unioned
      where (:q = '' or a ilike :like or b ilike :like)
      group by 1,2
      order by coalesce(max(last_cross), date '-infinity') desc, a, b
      limit :lim offset :off
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={
            "off": int(off), "lim": int(lim),
            "q": (q or "").strip(), "like": f"%{(q or '').strip()}%"
        })
    return df

st.session_state.setdefault("_pairs_ps", 50)
st.session_state.setdefault("_pairs_off", 0)
st.session_state.setdefault("_pairs_df", pd.DataFrame())
st.session_state.setdefault("_pairs_q", "")

c1, c2, c3 = st.columns([3,1,1])
with c1:
    new_q = st.text_input("Filter by fish_code", value=st.session_state["_pairs_q"])
with c2:
    new_ps = st.number_input("Rows/page", min_value=10, max_value=200, value=st.session_state["_pairs_ps"], step=10)
with c3:
    if st.button("↻ Refresh"):
        st.session_state.update({"_pairs_q": new_q, "_pairs_ps": int(new_ps), "_pairs_off": 0, "_pairs_df": pd.DataFrame()})

if st.session_state["_pairs_df"].empty:
    chunk = _conceptual_pairs_chunk(st.session_state["_pairs_off"], st.session_state["_pairs_ps"], st.session_state["_pairs_q"])
    st.session_state["_pairs_df"] = chunk.copy()
    st.session_state["_pairs_off"] += len(chunk)

pairs = st.session_state["_pairs_df"].copy()
if not pairs.empty and "Select" not in pairs.columns:
    pairs.insert(0, "Select", False)

pairs_view = pairs.rename(columns={"parent_a":"Parent A", "parent_b":"Parent B", "last_cross":"Last cross"})
sel = st.data_editor(
    pairs_view,
    width="stretch", hide_index=True,
    column_config={
        "Select": st.column_config.CheckboxColumn("✓", default=False),
        "Parent A": st.column_config.TextColumn("Parent A", disabled=True),
        "Parent B": st.column_config.TextColumn("Parent B", disabled=True),
        "Last cross": st.column_config.DateColumn("Last cross", disabled=True, format="YYYY-MM-DD")
    },
    key="conceptual_pairs_editor",
)
picked = sel[sel["Select"]]
if not picked.empty:
    a = str(picked.iloc[0]["Parent A"]).strip()
    b = str(picked.iloc[0]["Parent B"]).strip()
    st.session_state["mom_fish_code"] = a
    st.session_state["dad_fish_code"] = b

if st.button("Load more pairs"):
    chunk = _conceptual_pairs_chunk(st.session_state["_pairs_off"], st.session_state["_pairs_ps"], st.session_state["_pairs_q"])
    if not chunk.empty:
        st.session_state["_pairs_df"] = pd.concat([st.session_state["_pairs_df"], chunk], ignore_index=True)
        st.session_state["_pairs_off"] += len(chunk)
    else:
        st.info("No more pairs.")

# =============================================================================
# 1) Parent inputs (prefilled from handoff or table selection)
# =============================================================================
parent_a = st.text_input("Parent A fish_code", value=st.session_state.get("mom_fish_code") or pending.get("mom_fish_code") or "")
parent_b = st.text_input("Parent B fish_code", value=st.session_state.get("dad_fish_code") or pending.get("dad_fish_code") or "")
if not parent_a or not parent_b:
    st.info("Set Parent A and Parent B to continue.")
    st.stop()

# =============================================================================
# 2) Select Mother tank
# =============================================================================
st.markdown("### 2) Select **Mother** tank")
mothers = _load_live_tanks_for_fish([parent_a, parent_b]).copy()
if mothers.empty:
    st.warning("No live tanks found for either parent."); st.stop()
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
# 3) Select Father tank
# =============================================================================
st.markdown("### 3) Select **Father** tank")
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

if mother_tank_id == father_tank_id:
    st.error("Mother and Father cannot be the same tank."); st.stop()

# =============================================================================
# 4) Optional clutch genotype label
# =============================================================================
st.markdown("### 4) Define clutch genotype label")
geno_for_clutch = st.text_input("Clutch genotype label (optional)", value="", key="geno_label_for_clutch").strip()

# =============================================================================
# 5) Save tank_pair and create a cross_instance
# =============================================================================
st.markdown("### 5) Save pairing and create a cross")
left, right = st.columns([1,2])
with left:
    created_by_val = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown")
    note_val = st.text_input("Note (optional)", value="")
    can_save = bool(mother_tank_id and father_tank_id)

    if st.button("💾 Save mother/father pairing", type="primary", width="stretch", disabled=not can_save):
        try:
            inserted, tp_code = _upsert_one_pair(mother_tank_id, father_tank_id, created_by_val, note_val)
            if inserted:
                st.success(f"Saved tank_pair {tp_code}")
            else:
                st.success(f"Updated tank_pair {tp_code}")

            with _eng().begin() as cx:
                x = cx.execute(text("""
                    insert into public.cross_instances
                    (cross_id, id, tank_pair_code, cross_date, created_by, note)
                    values
                    (gen_random_uuid(), gen_random_uuid(), :tp_code, :d, :by, nullif(:note,''))
                    returning id, cross_run_code
                """), {"tp_code": tp_code, "d": str(_date.today()), "by": created_by_val, "note": note_val}).mappings().first()
            cross_instance_id = x["id"]
            cross_code = x.get("cross_run_code")

            sent_geno = (st.session_state.get("geno_label_for_clutch") or geno_for_clutch or "").strip()
            with _eng().begin() as cx:
                cl = cx.execute(text("""
                    insert into public.clutch_instances (
                        id, cross_instance_id, tank_pair_code, clutch_genotype_pretty
                    )
                    values (
                        gen_random_uuid(), :cid, :tp_code, nullif(:geno,'')
                    )
                    returning clutch_instance_code
                """), {"cid": cross_instance_id, "tp_code": tp_code, "geno": sent_geno}).mappings().first()

            if cl:
                st.success(f"→ Cross {cross_code or '(new)'}; clutch {cl['clutch_instance_code']} (genotype={sent_geno or '—'})")
            st.cache_data.clear()

        except Exception as e:
            st.exception(e)

with right:
    st.markdown("**Recent tank_pairs for these tanks**")
    vf = _pick_fish_view()
    geno_col = _fish_genotype_col(vf)
    mom_geno_expr = "''" if not geno_col else f"coalesce(vfm.{geno_col}, '')"
    dad_geno_expr = "''" if not geno_col else f"coalesce(vfd.{geno_col}, '')"
    mom_col, dad_col = _tankpair_parent_cols()

    sql_recent = text(f"""
      select
        tp.tank_pair_code,
        tp.status,
        vtm.fish_code  as mom_fish_code,
        vtm.tank_code  as mom_tank_code,
        {mom_geno_expr} as mom_genotype,
        vtf.fish_code  as dad_fish_code,
        vtf.tank_code  as dad_tank_code,
        {dad_geno_expr} as dad_genotype,
        tp.note,
        tp.created_by,
        tp.created_at
      from public.tank_pairs tp
      left join public.v_tanks vtm on vtm.tank_uuid = tp.{mom_col}
      left join public.v_tanks vtf on vtf.tank_uuid = tp.{dad_col}
      left join {vf} vfm on vfm.fish_code = vtm.fish_code
      left join {vf} vfd on vfd.fish_code = vtf.fish_code
      where tp.{mom_col} = cast(:mom as uuid)
         or tp.{dad_col} = cast(:dad as uuid)
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