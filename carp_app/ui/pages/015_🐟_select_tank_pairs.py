# =============================================================================
# 🧬 Select tank pairings — pick parents (from v_fish_rich), choose tanks, save cross/clutch
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date as _date
from typing import List, Optional

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

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🧬 Select tank pairings", page_icon="🧬", layout="wide")
st.title("🧬 Select tank pairings")

@st.cache_resource(show_spinner=False)
def _cached_engine():
    return get_engine()

def get_resource_engine():
    return get_engine()

def _eng():
    if not os.getenv("DB_URL"):
        st.error("DB_URL not set"); st.stop()
    return _cached_engine()

with _eng().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

@st.cache_data(show_spinner=False)
def _table_cols(schema: str, table: str) -> List[str]:
    with _eng().begin() as cx:
        df = pd.read_sql(
            text("""
                select column_name
                from information_schema.columns
                where table_schema = :s and table_name = :t
                order by ordinal_position
            """),
            cx, params={"s": schema, "t": table}
        )
    return df["column_name"].tolist()

@st.cache_data(show_spinner=False)
def _pick_fish_view() -> str:
    with _eng().begin() as cx:
        rows = pd.read_sql(
            text("""
                select table_name
                from information_schema.views
                where table_schema='public' and table_name in ('v_fish_rich','v_fish')
            """),
            cx
        )
    have = set(rows["table_name"].tolist())
    return "public.v_fish_rich" if "v_fish_rich" in have else "public.v_fish"

def _fish_pretty_col(view: str) -> Optional[str]:
    cols = _table_cols("public", view.split(".")[1])
    for c in ("transgene_pretty_name", "genotype_rollup"):
        if c in cols:
            return c
    return None

@st.cache_data(show_spinner=False)
def _search_fish_rich(q: Optional[str], limit: int) -> pd.DataFrame:
    view = _pick_fish_view()
    vtbl = view.split(".")[1]
    cols = _table_cols("public", vtbl)
    pick = _fish_pretty_col(view)
    pick_sel = f", b.{pick} as genotype" if pick else ", ''::text as genotype"
    hay = ["coalesce(b.fish_code,'')"]
    for c in ("fish_name","fish_nickname","genetic_background"):
        if c in cols:
            hay.append(f"coalesce(b.{c},'')")
    if pick:
        hay.append(f"coalesce(b.{pick},'')")
    hay_expr = " || ' ' || ".join(hay)
    where = ""
    params = {"lim": int(limit)}
    if q and q.strip():
        params["ql"] = f"%{q.strip()}%"
        where = f"where ({hay_expr}) ilike :ql"
    sql = text(f"""
        with base as (
          select b.fish_code,
                 {"b.fish_name" if "fish_name" in cols else "''::text as fish_name"},
                 {"b.fish_nickname" if "fish_nickname" in cols else "''::text as fish_nickname"},
                 {"b.genetic_background" if "genetic_background" in cols else "''::text as genetic_background"}
                 {pick_sel},
                 coalesce({"b.created_at" if "created_at" in cols else "now()"}, now()) as created_at
          from {view} b
          {where}
          order by coalesce({"b.created_at" if "created_at" in cols else "now()"}, now()) desc, b.fish_code
          limit :lim
        ),
        live as (
          select vt.fish_code,
                 count(*) as n_live,
                 string_agg(distinct vt.tank_code, ', ' order by vt.tank_code) as live_tanks
          from public.v_tanks vt
          where vt.status::text = any(array['active','new'])
          group by vt.fish_code
        )
        select base.fish_code as "fish_code",
               base.fish_name as "name",
               base.fish_nickname as "nickname",
               base.genetic_background as "background",
               base.genotype as "genotype",
               coalesce(live.n_live,0) as "live_tanks",
               coalesce(live.live_tanks,'') as "live_tank_codes",
               base.created_at as "created_at"
        from base
        left join live using (fish_code)
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include=["object","string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

@st.cache_data(show_spinner=False)
def _load_live_tanks_for_fish(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=["fish_code","tank_code","tank_id","status","created_at"])
    sql = text("""
        select
            vt.fish_code,
            vt.tank_code,
            vt.tank_uuid::text as tank_id,
            coalesce(vt.status::text,'') as status,
            vt.created_at
        from public.v_tanks vt
        where vt.fish_code = any(:codes)
          and vt.status::text = any(array['active','new'])
        order by vt.fish_code, vt.created_at desc nulls last
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": list({c for c in codes if c})})
    for c in df.select_dtypes(include=["object","string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _tankpair_parent_cols() -> tuple[str,str]:
    cols = set(_table_cols("public","tank_pairs"))
    for a,b in (("mother_tank_id","father_tank_id"),("tank_id_mother","tank_id_father")):
        if a in cols and b in cols:
            return a,b
    raise RuntimeError("public.tank_pairs lacks expected mother/father tank id columns")

def _find_existing_tank_pair(mother_id: str, father_id: str) -> Optional[str]:
    mom_col, dad_col = _tankpair_parent_cols()
    with _eng().begin() as cx:
        row = pd.read_sql(
            text(f"""
                select id::text
                from public.tank_pairs
                where {mom_col} = cast(:m as uuid)
                  and {dad_col} = cast(:d as uuid)
                  and coalesce(concept_id::text,'') = ''
                limit 1
            """), cx, params={"m": mother_id, "d": father_id}
        )
    return None if row.empty else row.iloc[0]["id"]

def _upsert_tank_pair(mother_tank_id: str, father_tank_id: str, created_by: str, note: str) -> tuple[bool,str]:
    existing_id = _find_existing_tank_pair(mother_tank_id, father_tank_id)
    with _eng().begin() as cx:
        if existing_id:
            cx.execute(
                text("""
                    update public.tank_pairs
                    set updated_at = now(), note = coalesce(nullif(:note,''), note)
                    where id = cast(:id as uuid)
                """), {"note": note, "id": existing_id}
            )
            tp_code = pd.read_sql(text("select tank_pair_code from public.tank_pairs where id = cast(:id as uuid)"),
                                  cx, params={"id": existing_id}).iloc[0]["tank_pair_code"]
            return False, str(tp_code)
        tp_code = cx.execute(
            text("""
                insert into public.tank_pairs(mother_tank_id, father_tank_id, status, created_by, note)
                values (cast(:m as uuid), cast(:d as uuid), 'selected', :by, nullif(:note,''))
                returning tank_pair_code
            """), {"m": mother_tank_id, "d": father_tank_id, "by": created_by, "note": note}
        ).scalar()
    return True, str(tp_code)

st.header("Step 1 — Select parents (from fish registry)")
qcol,lcol = st.columns([3,1])
with qcol:
    q = st.text_input("Filter by code/name/nickname/genotype/background", "")
with lcol:
    lim = int(st.number_input("Rows", min_value=50, max_value=2000, value=500, step=50))
df_fish = _search_fish_rich(q, lim)
if df_fish.empty:
    st.info("No fish match your filters."); st.stop()
view = df_fish.copy()
view.insert(0, "✓ Parent", False)
cfg = {
    "✓ Parent": st.column_config.CheckboxColumn("✓", default=False),
    "fish_code": st.column_config.TextColumn("fish_code", disabled=True),
    "name": st.column_config.TextColumn("name", disabled=True),
    "nickname": st.column_config.TextColumn("nickname", disabled=True),
    "background": st.column_config.TextColumn("background", disabled=True),
    "genotype": st.column_config.TextColumn("genotype", disabled=True),
    "live_tanks": st.column_config.NumberColumn("live tanks", format="%d"),
    "live_tank_codes": st.column_config.TextColumn("live tank codes", disabled=True),
    "created_at": st.column_config.DatetimeColumn("created_at", disabled=True, format="YYYY-MM-DD HH:mm"),
}
edit = st.data_editor(view, key="parent_pick_table", width="stretch", hide_index=True, column_config=cfg)
chosen = []
if not edit.empty and "✓ Parent" in edit.columns:
    chosen = edit.loc[edit["✓ Parent"] == True, "fish_code"].dropna().astype(str).tolist()
chosen = list(dict.fromkeys(chosen))[:2]
if len(chosen) < 2:
    st.info("Select two parents above to continue."); st.stop()
parent_a, parent_b = chosen[0], chosen[1]
st.success(f"Selected parents: {parent_a} × {parent_b}")

st.header("Step 2 — Choose Mother and Father tanks")
live = _load_live_tanks_for_fish([parent_a, parent_b])
if live.empty:
    st.warning("No live tanks found for these parents."); st.stop()
live = live.sort_values(["fish_code","created_at"], ascending=[True, False])

mcol, fcol = st.columns(2)
with mcol:
    st.subheader("Mother")
    mdf = live.copy()
    mdf.insert(0,"✓ Mother", False)
    mview = mdf[["✓ Mother","fish_code","tank_code","tank_id","status","created_at"]]
    msel = st.data_editor(
        mview, key="mother_table", width="stretch", hide_index=True,
        column_config={
            "✓ Mother": st.column_config.CheckboxColumn("✓", default=False),
            "fish_code": st.column_config.TextColumn("fish", disabled=True),
            "tank_code": st.column_config.TextColumn("tank", disabled=True),
            "tank_id":   st.column_config.TextColumn("tank_id", disabled=True),
            "status":    st.column_config.TextColumn("status", disabled=True),
            "created_at":st.column_config.DatetimeColumn("created", disabled=True, format="YYYY-MM-DD HH:mm"),
        }
    )
    selm = msel.loc[msel["✓ Mother"] == True] if not msel.empty else pd.DataFrame()
    if selm.empty:
        st.stop()
    mother = selm.iloc[0]
    mother_tank_id = str(mother["tank_id"])
    mother_fish = str(mother["fish_code"])

with fcol:
    st.subheader("Father")
    fdf = live[live["fish_code"].ne(mother_fish)].copy()
    fdf.insert(0,"✓ Father", False)
    fview = fdf[["✓ Father","fish_code","tank_code","tank_id","status","created_at"]]
    fsel = st.data_editor(
        fview, key="father_table", width="stretch", hide_index=True,
        column_config={
            "✓ Father": st.column_config.CheckboxColumn("✓", default=False),
            "fish_code": st.column_config.TextColumn("fish", disabled=True),
            "tank_code": st.column_config.TextColumn("tank", disabled=True),
            "tank_id":   st.column_config.TextColumn("tank_id", disabled=True),
            "status":    st.column_config.TextColumn("status", disabled=True),
            "created_at":st.column_config.DatetimeColumn("created", disabled=True, format="YYYY-MM-DD HH:mm"),
        }
    )
    selfa = fsel.loc[fsel["✓ Father"] == True] if not fsel.empty else pd.DataFrame()
    if selfa.empty:
        st.stop()
    father = selfa.iloc[0]
    father_tank_id = str(father["tank_id"])

if mother_tank_id == father_tank_id:
    st.error("Mother and Father cannot be the same tank."); st.stop()

st.header("Step 3 — Save pairing and create cross (and optional clutch)")
left, right = st.columns([1,2])
with left:
    created_by_val = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown")
    note_val = st.text_input("Note (optional)", value="")
    geno_label = st.text_input("Clutch genotype label (optional)", value="")
    if st.button("💾 Save pairing and create cross", type="primary"):
        try:
            inserted, tp_code = _upsert_tank_pair(mother_tank_id, father_tank_id, created_by_val, note_val)
            with _eng().begin() as cx:
                row = cx.execute(
                    text("""
                        insert into public.cross_instances
                        (cross_id, id, tank_pair_code, cross_date, created_by, note)
                        values (gen_random_uuid(), gen_random_uuid(), :tp, :d, :by, nullif(:note,''))
                        returning id, cross_run_code
                    """), {"tp": tp_code, "d": str(_date.today()), "by": created_by_val, "note": note_val}
                ).mappings().first()
            cross_id = row["id"]
            cross_code = row.get("cross_run_code")
            with _eng().begin() as cx:
                crow = cx.execute(
                    text("""
                        insert into public.clutch_instances
                        (id, cross_instance_id, tank_pair_code, clutch_genotype_pretty)
                        values (gen_random_uuid(), :cid, :tp, nullif(:geno,''))
                        returning clutch_instance_code
                    """),
                    {"cid": cross_id, "tp": tp_code, "geno": geno_label.strip()}
                ).mappings().first()
            st.success(f"Saved tank_pair {tp_code}; cross {cross_code or '(new)'}; clutch {crow['clutch_instance_code']}")
            st.session_state.pop("parent_pick_table", None)
            st.session_state.pop("mother_table", None)
            st.session_state.pop("father_table", None)
        except Exception as e:
            st.error(str(e))

with right:
    st.subheader("Recent activity for these tanks")
    mom_col, dad_col = _tankpair_parent_cols()
    vf = _pick_fish_view()
    gcol = _fish_pretty_col(vf)
    mg = "''" if not gcol else f"coalesce(vfm.{gcol},'')"
    fg = "''" if not gcol else f"coalesce(vff.{gcol},'')"
    sql = text(f"""
        select
          tp.tank_pair_code,
          vtm.fish_code as mother_fish,
          vtm.tank_code as mother_tank,
          {mg} as mother_genotype,
          vtf.fish_code as father_fish,
          vtf.tank_code as father_tank,
          {fg} as father_genotype,
          tp.status, tp.created_by, tp.created_at
        from public.tank_pairs tp
        left join public.v_tanks vtm on vtm.tank_uuid = tp.{mom_col}
        left join public.v_tanks vtf on vtf.tank_uuid = tp.{dad_col}
        left join {vf} vfm on vfm.fish_code = vtm.fish_code
        left join {vf} vff on vff.fish_code = vtf.fish_code
        where tp.{mom_col} = cast(:m as uuid) or tp.{dad_col} = cast(:d as uuid)
        order by tp.created_at desc nulls last
        limit 50
    """)
    with _eng().begin() as cx:
        recent = pd.read_sql(sql, cx, params={"m": mother_tank_id, "d": father_tank_id})
    if recent.empty:
        st.info("No recent pairings for these tanks yet.")
    else:
        st.dataframe(
            recent[[
                "tank_pair_code","mother_fish","mother_tank","mother_genotype",
                "father_fish","father_tank","father_genotype","status","created_by","created_at"
            ]],
            width="stretch", hide_index=True
        )