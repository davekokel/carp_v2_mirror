# carp_app/ui/pages/170_🔎_overview_tank_pairs.py
from __future__ import annotations

import sys, pathlib, os
from typing import List, Optional, Tuple, Set
import pandas as pd
import streamlit as st
from sqlalchemy import text

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# auth / engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — 🔎 Overview: Tank pairs", page_icon="🔎", layout="wide")
st.title("🔎 Overview: Tank pairs")

# sanity caption
with engine().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ── schema helpers ───────────────────────────────────────────────────────────
def _table_exists(schema: str, table: str) -> bool:
    with engine().begin() as cx:
        n = pd.read_sql(
            text("""
              select count(*)::int as n
              from information_schema.tables
              where table_schema=:s and table_name=:t
            """),
            cx, params={"s": schema, "t": table}
        )["n"][0]
    return n > 0

def _cols(schema: str, rel: str) -> Set[str]:
    with engine().begin() as cx:
        df = pd.read_sql(
            text("""
              select column_name
              from information_schema.columns
              where table_schema=:s and table_name=:r
            """),
            cx, params={"s": schema, "r": rel}
        )
    return set(df["column_name"].tolist())

def _tank_pair_parent_cols() -> Tuple[str, str]:
    c = _cols("public", "tank_pairs")
    for a, b in (("mother_tank_id","father_tank_id"),
                 ("tank_id_mother","tank_id_father")):
        if a in c and b in c:
            return a, b
    raise RuntimeError("public.tank_pairs must have parent UUID columns (mother_tank_id/father_tank_id or tank_id_mother/tank_id_father).")

have_tp       = _table_exists("public", "tank_pairs")
tp_cols       = _cols("public", "tank_pairs") if have_tp else set()
have_crosses  = _table_exists("public", "crosses")
have_clutches = _table_exists("public", "clutch_instances")
have_tp_code  = ("tank_pair_code" in tp_cols)

# ── filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([3,1,1,1])
    q   = c1.text_input("Search (pair/fish/tank/genotype)")
    d1  = c2.date_input("Created from", value=None) if "created_at" in tp_cols else None
    d2  = c3.date_input("Created to",   value=None) if "created_at" in tp_cols else None
    status_val = c4.selectbox("Status", ["(any)","selected","scheduled","retired","closed"], index=0) if "status" in tp_cols else "(any)"
    st.form_submit_button("Apply")

# ── build query (no dependency on v_tank_pairs) ──────────────────────────────
if not have_tp:
    st.info("No tank_pairs table found.")
    st.stop()

mom_col, dad_col = _tank_pair_parent_cols()

# filters
where = []
params = {}
if q and q.strip():
    ql = f"%{q.strip()}%"
    bag = []
    if have_tp_code:                   bag.append("coalesce(tp.tank_pair_code,'') ilike :q")
    if "fish_pair_code" in tp_cols:    bag.append("coalesce(tp.fish_pair_code,'') ilike :q")
    # fish/tank/genotype text match via joins later (in outer WHERE)
    params["q"] = ql
    # We'll apply outer filters too
if "created_at" in tp_cols and d1:
    where.append("tp.created_at >= :d1"); params["d1"] = str(d1)
if "created_at" in tp_cols and d2:
    where.append("tp.created_at <= :d2"); params["d2"] = str(d2)
if "status" in tp_cols and status_val != "(any)":
    where.append("coalesce(tp.status,'') = :st"); params["st"] = status_val
where_sql = (" where " + " AND ".join(where)) if where else ""

# ORDER BY
order_clause = "tp.created_at desc nulls last, tp.tank_pair_code" if "created_at" in tp_cols and have_tp_code else \
               "tp.created_at desc nulls last" if "created_at" in tp_cols else \
               "tp.tank_pair_code" if have_tp_code else "tp." + mom_col

sql = text(f"""
WITH tp AS (
  SELECT *
  FROM public.tank_pairs tp
  {where_sql}
),
-- mother/father tanks
tm AS (
  SELECT
    vt.tank_uuid::uuid AS tank_id,
    vt.tank_code,
    -- derive fish_code from tank_code "TANK(<code>)#N"
    regexp_replace(vt.tank_code, '^.*\\(([^)]+)\\).*$', '\\1')::text AS fish_code
  FROM public.v_tanks vt
),
-- genotype per fish (from v_fish_main)
geno AS (
  SELECT
    vm.fish_code,
    MAX(vm.genotype_pretty) AS genotype
  FROM public.v_fish_main vm
  GROUP BY vm.fish_code
)
SELECT
  {('tp.tank_pair_code' if have_tp_code else 'NULL::text')}      AS tank_pair_code,
  {('tp.fish_pair_code' if 'fish_pair_code' in tp_cols else 'NULL::text')} AS fish_pair_code,
  {('tp.status'         if 'status' in tp_cols else "'unknown'::text")}    AS status,
  {('tp.created_by'     if 'created_by' in tp_cols else 'NULL::text')}     AS created_by,
  {('tp.created_at'     if 'created_at' in tp_cols else 'NULL::timestamptz')} AS created_at,

  tm_m.fish_code  AS mom_fish_code,
  tm_m.tank_code  AS mom_tank_code,
  g_m.genotype    AS mom_genotype,

  tm_d.fish_code  AS dad_fish_code,
  tm_d.tank_code  AS dad_tank_code,
  g_d.genotype    AS dad_genotype

FROM tp
LEFT JOIN tm   AS tm_m ON tm_m.tank_id = tp.{mom_col}
LEFT JOIN tm   AS tm_d ON tm_d.tank_id = tp.{dad_col}
LEFT JOIN geno AS g_m  ON g_m.fish_code = tm_m.fish_code
LEFT JOIN geno AS g_d  ON g_d.fish_code = tm_d.fish_code

/* optional free-text search across joined fields */
{"WHERE (" + " OR ".join([
    "coalesce(tp.tank_pair_code,'') ilike :q"       if have_tp_code else None,
    "coalesce(tp.fish_pair_code,'') ilike :q"       if 'fish_pair_code' in tp_cols else None,
    "coalesce(tm_m.fish_code,'') ilike :q",
    "coalesce(tm_d.fish_code,'') ilike :q",
    "coalesce(tm_m.tank_code,'') ilike :q",
    "coalesce(tm_d.tank_code,'') ilike :q",
    "coalesce(g_m.genotype,'') ilike :q",
    "coalesce(g_d.genotype,'') ilike :q",
]) + ")" if 'q' in params else ""}

ORDER BY {order_clause}
LIMIT :lim
""")

params["lim"] = 500

with engine().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} pair(s)")
if df.empty:
    st.info("No tank pairs match your filters."); st.stop()

cols = [
    "tank_pair_code","fish_pair_code","status","created_at","created_by",
    "mom_fish_code","mom_tank_code","mom_genotype",
    "dad_fish_code","dad_tank_code","dad_genotype",
]
show = [c for c in cols if c in df.columns]
st.dataframe(df[show], use_container_width=True, hide_index=True)