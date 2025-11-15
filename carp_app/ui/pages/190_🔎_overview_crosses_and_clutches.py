# carp_app/ui/pages/190_🔎_overview_crosses_and_clutches.py
from __future__ import annotations

import sys, pathlib
from typing import Any, List, Tuple

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

# ── Auth + page setup ────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🔎 Cross & Clutch Instances",
    page_icon="🧪",
    layout="wide",
)
st.title("🔎 Cross & Clutch Instances")

with engine().begin() as cx:
    dbg = pd.read_sql(
        text("select current_database() db, inet_server_addr() host, current_user u"),
        cx,
    )
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ── helpers ──────────────────────────────────────────────────────────────────
def _safe(q: str, p=None) -> pd.DataFrame:
    with engine().begin() as cx:
        return pd.read_sql(text(q), cx, params=p or {})

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    q_like = c1.text_input(
        "Search (TP / fish / tank / cross / clutch)",
        placeholder="TP-000001, FSH-2025-0001, tank code, cross code, clutch code…",
    )
    d_from = c2.date_input("From", value=None)
    d_to   = c3.date_input("To",   value=None)
    lim    = int(c4.number_input("Limit", min_value=10, max_value=2000, value=200, step=50))
    submitted = st.form_submit_button("Apply")

params = {"lim": lim}
w: List[str] = []

if q_like and q_like.strip():
    params["q"] = f"%{q_like.strip()}%"
    w.append("""(
        coalesce(tank_pair_code,'')    ilike :q OR
        coalesce(mom_fish_code,'')     ilike :q OR
        coalesce(dad_fish_code,'')     ilike :q OR
        coalesce(mom_tank_code,'')     ilike :q OR
        coalesce(dad_tank_code,'')     ilike :q OR
        coalesce(mom_genotype,'')      ilike :q OR
        coalesce(dad_genotype,'')      ilike :q OR
        coalesce(mom_fusions,'')       ilike :q OR
        coalesce(dad_fusions,'')       ilike :q OR
        coalesce(clutch_genotype,'')   ilike :q OR
        coalesce(clutch_genotype_pretty,'') ilike :q OR
        coalesce(cross_code,'')        ilike :q OR
        coalesce(clutch_code,'')       ilike :q
    )""")

if d_from:
    params["d1"] = str(d_from)
    w.append("(cross_date >= :d1)")
if d_to:
    params["d2"] = str(d_to)
    w.append("(cross_date < (:d2::date + interval '1 day'))")

WHERE = (" WHERE " + " AND ".join(w)) if w else ""

SQL = f"""
WITH base AS (
  SELECT *
  FROM public.v_clutches_overview
  {WHERE}
  ORDER BY cross_date DESC, clutch_created_at DESC NULLS LAST
  LIMIT :lim
),
allele_counts AS (
  SELECT
    ceg.clutch_instance_id,
    COUNT(DISTINCT (ceg.transgene_base_code, ceg.allele_number))::int AS n_alleles
  FROM public.clutch_expected_genotypes ceg
  GROUP BY ceg.clutch_instance_id
),
pattern_counts AS (
  SELECT
    ceg.clutch_instance_id,
    COUNT(DISTINCT ceg.pattern_index)::int AS n_genotypes
  FROM public.clutch_expected_genotypes ceg
  WHERE ceg.pattern_index IS NOT NULL
  GROUP BY ceg.clutch_instance_id
)
SELECT
  -- display clutch code: stored code or CI-<idprefix> fallback
  COALESCE(
    b.clutch_code,
    'CL-' || LEFT(b.clutch_instance_id::text, 8)
  ) AS clutch_code_disp,

  -- display cross label: cross_code or TP@date
  COALESCE(
    b.cross_code,
    b.tank_pair_code || ' @ ' || COALESCE(b.cross_date::text, '')
  ) AS cross_code_disp,

  COALESCE(ac.n_alleles,   0) AS n_alleles,
  COALESCE(pc.n_genotypes, 0) AS n_genotypes,

  -- alleles rollup: use clutch_genotype* if present, otherwise mom×dad fallback
  CASE
    WHEN ac.n_alleles IS NULL OR ac.n_alleles = 0 THEN
      TRIM(
        BOTH ' × ' FROM (
          COALESCE(NULLIF(b.mom_genotype,''), '?') || ' × ' ||
          COALESCE(NULLIF(b.dad_genotype,''), '?')
        )
      )
    WHEN ac.n_alleles = 1 THEN
      COALESCE(b.clutch_genotype_pretty, b.clutch_genotype)
    WHEN ac.n_alleles = 2 THEN
      REPLACE(COALESCE(b.clutch_genotype_pretty, b.clutch_genotype), ', ', ' + ')
    ELSE
      'mixed (' || ac.n_alleles || ' alleles)'
  END AS alleles_rollup,

  b.*
FROM base b
LEFT JOIN allele_counts  ac ON ac.clutch_instance_id = b.clutch_instance_id
LEFT JOIN pattern_counts pc ON pc.clutch_instance_id = b.clutch_instance_id
ORDER BY b.cross_date DESC, b.clutch_created_at DESC NULLS LAST;
"""

df = _safe(SQL, params)

st.caption(f"{len(df)} instance(s) from v_clutches_overview")
if df.empty:
    st.info("No cross / clutch instances yet.")
    st.stop()

# ── Grid (read-only) ─────────────────────────────────────────────────────────
sel_col = "✓ Select"
grid = df.copy()
if sel_col not in grid.columns:
    grid.insert(0, sel_col, False)

display_cols = [
    sel_col,
    "clutch_code_disp",
    "cross_date",
    "cross_code_disp",
    "tank_pair_code",
    "mom_fish_code",
    "dad_fish_code",
    "n_alleles",
    "n_genotypes",
    "alleles_rollup",
    "mom_fusions",
    "dad_fusions",
    "clutch_created_at",
]

ro = st.data_editor(
    grid[display_cols],
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        sel_col:             st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code_disp":  st.column_config.TextColumn("Clutch code", disabled=True),
        "cross_date":        st.column_config.DateColumn("Cross date", disabled=True, format="YYYY-MM-DD"),
        "cross_code_disp":   st.column_config.TextColumn("Cross code", disabled=True),
        "tank_pair_code":    st.column_config.TextColumn("TP code", disabled=True),
        "mom_fish_code":     st.column_config.TextColumn("Mom FSH", disabled=True),
        "dad_fish_code":     st.column_config.TextColumn("Dad FSH", disabled=True),
        "n_alleles":         st.column_config.NumberColumn("n_alleles", disabled=True),
        "n_genotypes":       st.column_config.NumberColumn("n_genotypes", disabled=True),
        "alleles_rollup":    st.column_config.TextColumn("Alleles rollup", disabled=True, width="large"),
        "mom_fusions":       st.column_config.TextColumn("Mom fusions", disabled=True),
        "dad_fusions":       st.column_config.TextColumn("Dad fusions", disabled=True),
        "clutch_created_at": st.column_config.DatetimeColumn("Clutch created", disabled=True),
    },
    key="v_clutches_overview_grid",
)

# selection mask is applied back to df so we retain hidden columns
sel_mask = ro.get(sel_col, pd.Series(False, index=ro.index)).fillna(False).astype(bool)
picked = df[sel_mask.values]

# ── Details split into 3 stacked tables ──────────────────────────────────────
st.divider()
st.subheader("Details")

if len(picked) == 0:
    st.info("Select a single row above to view details.")
elif len(picked) > 1:
    st.warning("Multiple rows selected. Please select just one to view details.")
else:
    sel = picked.iloc[0].to_dict()

    def _pivot(title: str, rows: List[Tuple[str, Any]]):
        dfp = pd.DataFrame(rows, columns=["Field", "Value"])
        st.subheader(title)
        st.dataframe(dfp, hide_index=True, use_container_width=True)

    # Mother profile — genotype + fusions
    mom_rows = [
        ("Fish code",          sel.get("mom_fish_code")),
        ("Tank code",          sel.get("mom_tank_code")),
        ("Nickname",           sel.get("mom_nickname")),
        ("Genetic background", sel.get("mom_genetic_background")),
        ("Line building stage",sel.get("mom_line_building_stage")),
        ("Birthday",           sel.get("mom_birthday")),
        ("Genotype",           sel.get("mom_genotype")),
        ("Fusions",            sel.get("mom_fusions")),
    ]
    _pivot("Mother — profile", mom_rows)

    # Father profile — genotype + fusions
    dad_rows = [
        ("Fish code",          sel.get("dad_fish_code")),
        ("Tank code",          sel.get("dad_tank_code")),
        ("Nickname",           sel.get("dad_nickname")),
        ("Genetic background", sel.get("dad_genetic_background")),
        ("Line building stage",sel.get("dad_line_building_stage")),
        ("Birthday",           sel.get("dad_birthday")),
        ("Genotype",           sel.get("dad_genotype")),
        ("Fusions",            sel.get("dad_fusions")),
    ]
    _pivot("Father — profile", dad_rows)

    # Clutch / Cross — metadata
    clutch_rows = [
        ("Cross code",      sel.get("cross_code_disp")),
        ("Cross date",      sel.get("cross_date")),
        ("Cross created",   sel.get("cross_created_at")),
        ("Tank pair code",  sel.get("tank_pair_code")),
        ("Clutch code",     sel.get("clutch_code_disp")),
        ("Clutch created",  sel.get("clutch_created_at")),
        ("n_alleles",         sel.get("n_alleles")),
        ("n_genotypes",       sel.get("n_genotypes")),
        ("Alleles rollup",    sel.get("alleles_rollup")),
        ("Mother genotype",   sel.get("mom_genotype")),
        ("Father genotype",   sel.get("dad_genotype")),
        ("Mother fusions",    sel.get("mom_fusions")),
        ("Father fusions",    sel.get("dad_fusions")),
    ]
    _pivot("Clutch / Cross — metadata", clutch_rows)