# carp_app/ui/pages/190_🔎_overview_crosses_and_clutches.py
# 🔎 Cross & Clutch Instances (direct joins; crosses + clutch_instances + tank_pairs + v_tanks + v_fish_main)
from __future__ import annotations

import sys, pathlib, os
from datetime import date, timedelta
from typing import Any, List, Optional, Set, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.elements import TextClause

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

# ── Auth + page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — 🔎 Cross & Clutch Instances", page_icon="🧪", layout="wide")
st.title("🔎 Cross & Clutch Instances")

with engine().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ── DB helpers ───────────────────────────────────────────────────────────────
def _treatments_pk_col() -> str:
    with engine().begin() as cx:
        df = _safe(cx, """
          SELECT column_name
          FROM information_schema.columns
          WHERE table_schema='public' AND table_name='treatments'
                AND column_name IN ('id','treatment_id')
          ORDER BY CASE column_name WHEN 'id' THEN 0 ELSE 1 END
          LIMIT 1
        """)
    if df.empty:
        # fallback: no recognized PK column; we won't show treatments
        return ""
    return df["column_name"].iat[0]

def _safe(cx, q: str | TextClause, p=None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

def _table_exists(schema: str, table: str) -> bool:
    with engine().begin() as cx:
        n = _safe(cx, """
          select count(*)::int as n
          from information_schema.tables
          where table_schema=:s and table_name=:t
        """, {"s": schema, "t": table})["n"][0]
    return n > 0

def _cols(schema: str, rel: str) -> Set[str]:
    with engine().begin() as cx:
        df = _safe(cx, """
          select column_name
          from information_schema.columns
          where table_schema=:s and table_name=:r
        """, {"s": schema, "r": rel})
    return set(df["column_name"].tolist())

def _tank_pair_parent_cols() -> Tuple[str, str]:
    c = _cols("public", "tank_pairs")
    for a, b in (("mother_tank_id","father_tank_id"),
                 ("tank_id_mother","tank_id_father")):
        if a in c and b in c:
            return a, b
    raise RuntimeError("public.tank_pairs must have mother/father tank UUID columns (e.g., mother_tank_id/father_tank_id).")

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([2,1,1,1])
    q   = c1.text_input("Search (TP/fish/tank/cross/clutch/genotype)")
    d1  = c2.date_input("From", value=None)
    d2  = c3.date_input("To",   value=None)
    lim = int(c4.number_input("Limit", min_value=10, max_value=2000, value=200, step=50))
    st.form_submit_button("Apply")

where_parts: list[str] = []
params: dict[str, Any] = {"lim": lim}

like = f"%{q.strip()}%" if q and q.strip() else None
if like:
    params["q"] = like
    where_parts.append("""(
      cr.tank_pair_code ilike :q OR
      coalesce(tm_m.fish_code,'') ilike :q OR coalesce(tm_d.fish_code,'') ilike :q OR
      coalesce(tm_m.tank_code,'') ilike :q OR coalesce(tm_d.tank_code,'') ilike :q OR
      coalesce(g_m.genotype,'')  ilike :q OR coalesce(g_d.genotype,'')  ilike :q OR
      coalesce(cl.clutch_genotype_pretty,'') ilike :q OR
      coalesce(cr.cross_run_code,'') ilike :q OR
      coalesce(cl.clutch_instance_code,'') ilike :q
    )""")

if d1:
    params["d1"] = str(d1)
    where_parts.append("(cr.cross_date >= :d1)")
if d2:
    params["d2"] = str(d2)
    where_parts.append("(cr.cross_date <= :d2)")

WHERE_SQL = (" where " + " and ".join(where_parts)) if where_parts else ""

# ── Query (direct joins; NO v_tank_pairs) ────────────────────────────────────
if not (_table_exists("public", "crosses") and _table_exists("public","tank_pairs") and _table_exists("public","clutch_instances")):
    st.info("Missing one or more required tables: crosses, tank_pairs, clutch_instances.")
    st.stop()

mom_col, dad_col = _tank_pair_parent_cols()

sql = text(f"""
  WITH tm AS (  -- tank → (fish_code, tank_code)
    SELECT
      vt.tank_uuid::uuid AS tank_id,
      vt.tank_code,
      regexp_replace(vt.tank_code, '^.*\\(([^)]+)\\).*$', '\\1')::text AS fish_code
    FROM public.v_tanks vt
  ),
  geno AS (     -- genotype per fish
    SELECT vm.fish_code, MAX(vm.genotype_pretty) AS genotype
    FROM public.v_fish_main vm
    GROUP BY vm.fish_code
  ),
  base AS (
    SELECT
      cr.id                           AS cross_id,
      cr.cross_run_code               AS cross_code,
      cr.tank_pair_code               AS tank_pair_code,

      tm_m.fish_code                  AS mom_fish_code,
      tm_d.fish_code                  AS dad_fish_code,
      tm_m.tank_code                  AS mom_tank_code,
      tm_d.tank_code                  AS dad_tank_code,
      COALESCE(g_m.genotype,'')       AS mom_genotype,
      COALESCE(g_d.genotype,'')       AS dad_genotype,

      cl.clutch_genotype_pretty       AS clutch_genotype,
      cr.cross_date                   AS cross_date,
      cr.created_at                   AS cross_created_at,
      cl.id                           AS clutch_instance_id,
      cl.clutch_instance_code         AS clutch_code,
      cl.created_at                   AS clutch_created_at
    FROM public.crosses cr
    LEFT JOIN public.clutch_instances cl
           ON cl.cross_instance_id = cr.id
    LEFT JOIN public.tank_pairs tp
           ON tp.tank_pair_code = cr.tank_pair_code
    LEFT JOIN tm AS tm_m
           ON tm_m.tank_id = tp.{mom_col}
    LEFT JOIN tm AS tm_d
           ON tm_d.tank_id = tp.{dad_col}
    LEFT JOIN geno AS g_m
           ON g_m.fish_code = tm_m.fish_code
    LEFT JOIN geno AS g_d
           ON g_d.fish_code = tm_d.fish_code
    {WHERE_SQL}
  )
  SELECT *
  FROM base
  ORDER BY
    cross_date DESC NULLS LAST,
    COALESCE(clutch_created_at, cross_created_at) DESC NULLS LAST
  LIMIT :lim
""")

with engine().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} instance(s)")
if df.empty:
    st.info("No instances yet."); st.stop()

# ── Display + Selection (table remains as-is, read-only) ─────────────────────
sel_col = "✓ Select"
grid = df.copy()
if sel_col not in grid.columns:
    grid.insert(0, sel_col, False)

first_cols = ["clutch_code", "clutch_genotype", "cross_date", "cross_code"]
ordered = [c for c in first_cols if c in grid.columns]
rest = [c for c in grid.columns if c not in ordered and c != sel_col]
display_cols = [sel_col] + ordered + rest

ro = st.data_editor(
    grid[display_cols],
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        sel_col:              st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code":        st.column_config.TextColumn("Clutch code", disabled=True),
        "clutch_genotype":    st.column_config.TextColumn("Clutch genotype", disabled=True, width="large"),
        "cross_date":         st.column_config.DateColumn("Cross date", disabled=True, format="YYYY-MM-DD"),
        "cross_code":         st.column_config.TextColumn("Cross code", disabled=True),
        "tank_pair_code":     st.column_config.TextColumn("TP code", disabled=True),
        "mom_fish_code":      st.column_config.TextColumn("Mom FSH", disabled=True),
        "dad_fish_code":      st.column_config.TextColumn("Dad FSH", disabled=True),
        "mom_tank_code":      st.column_config.TextColumn("Mom tank", disabled=True),
        "dad_tank_code":      st.column_config.TextColumn("Dad tank", disabled=True),
        "mom_genotype":       st.column_config.TextColumn("Mom genotype", disabled=True, width="large"),
        "dad_genotype":       st.column_config.TextColumn("Dad genotype", disabled=True, width="large"),
        "clutch_created_at":  st.column_config.DatetimeColumn("Clutch created", disabled=True),
        "cross_created_at":   st.column_config.DatetimeColumn("Cross created", disabled=True),
      },
    key="cross_clutch_instances_ro",
)
mask = ro.get(sel_col, pd.Series(False, index=ro.index)).fillna(False).astype(bool)
picked = ro[mask]

# ── Details section (pivot + linked rows) ────────────────────────────────────
st.divider()
st.subheader("Details")

if len(picked) == 0:
    st.info("Select a single row above to view details.")
elif len(picked) > 1:
    st.warning("Multiple rows selected. Please select just one to view details.")
else:
    sel = picked.iloc[0].to_dict()
    cross_id = sel.get("cross_id")
    cross_code = sel.get("cross_code")
    clutch_code = sel.get("clutch_code")

    # Pivot summary for the selected cross
    summary_pairs = [
        ("Cross code",       cross_code),
        ("Cross date",       sel.get("cross_date")),
        ("Tank pair code",   sel.get("tank_pair_code")),
        ("Mom tank",         sel.get("mom_tank_code")),
        ("Dad tank",         sel.get("dad_tank_code")),
        ("Mom fish",         sel.get("mom_fish_code")),
        ("Dad fish",         sel.get("dad_fish_code")),
        ("Mom genotype",     sel.get("mom_genotype")),
        ("Dad genotype",     sel.get("dad_genotype")),
        ("Clutch code (this row)", clutch_code),
        ("Clutch genotype",  sel.get("clutch_genotype")),
        ("Cross created",    sel.get("cross_created_at")),
        ("Clutch created",   sel.get("clutch_created_at")),
    ]
    pivot_df = pd.DataFrame(summary_pairs, columns=["Field", "Value"])
    st.dataframe(pivot_df, hide_index=True, use_container_width=True)

    # Linked rows: all clutches for this cross_id
    with engine().begin() as cx:
        clutches = _safe(cx, """
          SELECT
            cl.id::text              AS clutch_instance_id,
            cl.clutch_instance_code  AS clutch_code,
            cl.created_at,
            COALESCE(cl.clutch_genotype_pretty,'') AS clutch_genotype
          FROM public.clutch_instances cl
          WHERE cl.cross_instance_id = :cid
          ORDER BY cl.created_at
        """, {"cid": cross_id})

        st.markdown("**Clutch instances for this cross**")
    if clutches.empty:
        st.info("No clutch instances linked to this cross yet.")
    else:
        st.dataframe(
            clutches[["clutch_code","clutch_genotype","created_at"]],
            hide_index=True, use_container_width=True
        )

        # Optional: show treatments per clutch if the tables exist
        if _table_exists("public","join_clutch_treatments") and _table_exists("public","treatments"):
            clutch_ids = clutches["clutch_instance_id"].tolist()
            if clutch_ids:
                pk = _treatments_pk_col()
                if pk:
                    with engine().begin() as cx:
                        tr = _safe(cx, f"""
                          SELECT
                            j.clutch_instance_id::text,
                            t.kind_code,
                            t.name,
                            COALESCE(t.plasmid_id::text,'') AS plasmid_id,
                            COALESCE(t.rna_id::text,'')     AS rna_id,
                            j.created_at
                          FROM public.join_clutch_treatments j
                          JOIN public.treatments t ON t.{pk} = j.treatment_id
                          WHERE j.clutch_instance_id = ANY(:ids)
                          ORDER BY j.created_at
                        """, {"ids": clutch_ids})
                    st.markdown("**Treatments for selected cross’s clutches**")
                    if tr.empty:
                        st.info("No treatments linked to these clutches.")
                    else:
                        st.dataframe(
                            tr[["clutch_instance_id","kind_code","name","plasmid_id","rna_id","created_at"]],
                            hide_index=True, use_container_width=True
                        )
                else:
                    st.info("Couldn’t detect a primary key column for public.treatments (expected id or treatment_id); skipping treatments.")