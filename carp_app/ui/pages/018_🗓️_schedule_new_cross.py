# =============================================================================
# 🗓 Schedule new cross (uses TP codes; CX keyed by tank_pair_code)
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.elements import TextClause

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

# ── Auth + page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🗓 Schedule new cross", page_icon="🗓", layout="wide")
st.title("🗓 Schedule new cross")

# ── Engine ───────────────────────────────────────────────────────────────────
if not os.getenv("DB_URL"):
    st.error("DB_URL not set"); st.stop()
eng: Engine = get_engine()
with eng.begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

def _safe(cx, sql_or_text, params=None) -> pd.DataFrame:
    q = sql_or_text if isinstance(sql_or_text, TextClause) else text(sql_or_text)
    return pd.read_sql(q, cx, params=params or {})

@st.cache_data(show_spinner=False)
def _vtp_cols() -> set[str]:
    with eng.begin() as cx:
        df = pd.read_sql(text("""
            select column_name
            from information_schema.columns
            where table_schema='public' and table_name='v_tank_pairs'
        """), cx)
    return set(df["column_name"].tolist())

cols_vtp = _vtp_cols()
def _has(c: str) -> bool: return c in cols_vtp
def _pick(cands: list[str], cast: str, alias: str) -> str:
    for c in cands:
        if _has(c): return f"v.{c}::{cast} as {alias}"
    return f"null::{cast} as {alias}"

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2 = st.columns([3,1])
    q = c1.text_input("Search tank pairs (code / fish / tank)")
    limit = int(c2.number_input("Limit", min_value=10, max_value=2000, value=200, step=50))
    st.form_submit_button("Apply", use_container_width=True)

# ── Load candidate tank pairs from v_tank_pairs (column-adaptive) ────────────
select_parts = [
    _pick(["tank_pair_code"], "text", "tank_pair_code"),
    _pick(["fish_pair_code"], "text", "fish_pair_code"),
    _pick(["mom_fish_code"], "text", "mom_fish_code"),
    _pick(["mom_tank_code","mother_tank_code"], "text", "mom_tank_code"),
    "''::text as mom_genotype",
    _pick(["dad_fish_code"], "text", "dad_fish_code"),
    _pick(["dad_tank_code","father_tank_code"], "text", "dad_tank_code"),
    "''::text as dad_genotype",
    _pick(["created_at","tank_pair_created_at","pair_created_at"], "timestamptz", "created_at"),
]
where_parts = [
    "(:q = '' OR",
    " v.tank_pair_code ilike :ql OR",
    " v.fish_pair_code ilike :ql OR",
    " v.mom_fish_code  ilike :ql OR",
    " v.dad_fish_code  ilike :ql OR",
    f" {('v.mom_tank_code' if _has('mom_tank_code') else 'v.mother_tank_code')} ilike :ql OR",
    f" {('v.dad_tank_code' if _has('dad_tank_code') else 'v.father_tank_code')} ilike :ql)",
]
order_by = (
    "v.created_at desc nulls last" if _has("created_at")
    else "v.tank_pair_created_at desc nulls last" if _has("tank_pair_created_at")
    else "v.pair_created_at desc nulls last" if _has("pair_created_at")
    else "v.tank_pair_code asc"
)
sql_pairs = text(f"""
  select
    {", ".join(select_parts)}
  from public.v_tank_pairs v
  where {' '.join(where_parts)}
  order by {order_by}
  limit :lim
""")
with eng.begin() as cx:
    pairs = _safe(cx, sql_pairs, {"q": (q or ""), "ql": f"%{q or ''}%", "lim": limit})

st.subheader("1) Pick a tank pair")
if pairs.empty:
    st.info("No tank pairs. Create some on *Select tank pairings* first.")
    st.stop()

pairs_view = pairs.copy()
pairs_view["pair_fish"]  = (pairs_view["mom_fish_code"].fillna("") + " × " +
                            pairs_view["dad_fish_code"].fillna(""))
pairs_view["pair_tanks"] = (pairs_view["mom_tank_code"].fillna("") + " × " +
                            pairs_view["dad_tank_code"].fillna(""))
pairs_view["genotype"]   = (
    pairs_view["mom_genotype"].fillna("").replace("", pd.NA).astype("object")
    .combine(pairs_view["dad_genotype"].fillna("").replace("", pd.NA).astype("object"),
             lambda a,b: f"{a} × {b}" if pd.notna(a) and pd.notna(b) else (a if pd.notna(a) else b))
)
pairs_view.insert(0,"✓ Select", False)
pairs_edit = st.data_editor(
    pairs_view[["✓ Select","tank_pair_code","fish_pair_code","pair_fish","pair_tanks","genotype","created_at"]],
    hide_index=True, use_container_width=True,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)}
)
mask = pairs_edit["✓ Select"].fillna(False)
picked = pairs_view.loc[mask].head(1)
if picked.empty:
    st.info("Select one tank pair above to continue."); st.stop()

tp_code = str(picked.iloc[0]["tank_pair_code"])
st.success(f"Selected **{tp_code}** — {picked.iloc[0]['pair_fish']}")

# ── Options ──────────────────────────────────────────────────────────────────
st.subheader("2) Choose run date & options")
c1, c2 = st.columns([1,2])
run_date: date = c1.date_input("Run date", value=date.today())
make_clutch = c2.checkbox("Also create clutch now", value=True)
note = st.text_input("Run note (optional)")

# ── Action ───────────────────────────────────────────────────────────────────
if st.button("⏱ Schedule cross" + (" + clutch" if make_clutch else ""), type="primary"):
    creator = (user.get('email') or user.get('id') or 'unknown')
    try:
        with eng.begin() as cx:
            row = _safe(cx, """
              insert into public.cross_instances
                (cross_id, id, tank_pair_code, cross_date, created_by, note)
              values
                (gen_random_uuid(), gen_random_uuid(), :tp_code, :d, :by, nullif(:note,''))
              returning id, cross_run_code, cross_date, created_at
            """, {"tp_code": tp_code, "d": str(run_date), "by": creator, "note": note})
            if row.empty:
                st.error("Insert failed (no cross row returned)."); st.stop()
            cross_id   = str(row.iloc[0]["id"])
            cross_code = str(row.iloc[0]["cross_run_code"])

            if make_clutch:
                cl = _safe(cx, """
                  insert into public.clutch_instances (id, cross_instance_id, tank_pair_code)
                  values (gen_random_uuid(), :cid, :tp_code)
                  returning id, clutch_instance_code, created_at
                """, {"cid": cross_id, "tp_code": tp_code})
                if cl.empty:
                    st.warning(f"Cross {cross_code} saved; clutch insert returned no row.")
                else:
                    st.success(f"Saved: **{cross_code}**; clutch **{cl.iloc[0]['clutch_instance_code']}** "
                               f"(created {cl.iloc[0]['created_at']:%Y-%m-%d})")

        with eng.begin() as cx:
            preview = _safe(cx, """
              select
                ci.tank_pair_code,
                ci.cross_run_code as cross_code,
                to_char(ci.cross_date,'YYYY-MM-DD') as cross_date,
                cl.clutch_instance_code as clutch_code,
                to_char(coalesce(cl.created_at, ci.created_at),'YYYY-MM-DD') as created
              from public.cross_instances ci
              left join public.clutch_instances cl on cl.cross_instance_id = ci.id
              order by ci.created_at desc nulls last
              limit 5
            """)
        st.subheader("Recent CX events")
        st.dataframe(preview, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Schedule failed: {e}")