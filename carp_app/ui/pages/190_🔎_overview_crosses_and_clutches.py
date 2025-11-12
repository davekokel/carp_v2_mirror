# carp_app/ui/pages/190_🔎_overview_crosses_and_clutches.py
from __future__ import annotations

import sys, pathlib
from typing import Any, List

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

# ── Auth + page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — 🔎 Cross & Clutch Instances", page_icon="🧪", layout="wide")
st.title("🔎 Cross & Clutch Instances")

with engine().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ── helpers ──────────────────────────────────────────────────────────────────
def _safe(q: str, p=None) -> pd.DataFrame:
    with engine().begin() as cx:
        return pd.read_sql(text(q), cx, params=p or {})

def _cols_exists(df: pd.DataFrame, cols: List[str]) -> List[str]:
    have = set(df.columns)
    return [c for c in cols if c in have]

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([2,1,1,1])
    q_like = c1.text_input("Search (TP / fish / tank / cross / clutch / genotype)")
    d_from = c2.date_input("From", value=None)
    d_to   = c3.date_input("To",   value=None)
    lim    = int(c4.number_input("Limit", min_value=10, max_value=2000, value=200, step=50))
    submitted = st.form_submit_button("Apply")

params = {"lim": lim}
w = []

if q_like and q_like.strip():
    params["q"] = f"%{q_like.strip()}%"
    w.append("""(
        coalesce(tank_pair_code,'') ilike :q OR
        coalesce(mom_fish_code,'')  ilike :q OR
        coalesce(dad_fish_code,'')  ilike :q OR
        coalesce(mom_tank_code,'')  ilike :q OR
        coalesce(dad_tank_code,'')  ilike :q OR
        coalesce(mom_genotype,'')   ilike :q OR
        coalesce(dad_genotype,'')   ilike :q OR
        coalesce(clutch_genotype,'') ilike :q OR
        coalesce(cross_code,'')     ilike :q OR
        coalesce(clutch_code,'')    ilike :q
    )""")

if d_from:
    params["d1"] = str(d_from)
    w.append("(cross_date >= :d1)")
if d_to:
    params["d2"] = str(d_to)
    w.append("(cross_date < (:d2::date + interval '1 day'))")

WHERE = (" WHERE " + " AND ".join(w)) if w else ""
SQL = f"""
SELECT *
FROM public.v_clutches_overview
{WHERE}
ORDER BY cross_date DESC, clutch_created_at DESC NULLS LAST
LIMIT :lim
"""

df = _safe(SQL, params)

st.caption(f"{len(df)} instance(s) from v_clutches_overview")
if df.empty:
    st.info("No instances yet."); st.stop()

# ── Grid (read-only) ─────────────────────────────────────────────────────────
sel_col = "✓ Select"
grid = df.copy()
if sel_col not in grid.columns:
    grid.insert(0, sel_col, False)

primary = _cols_exists(grid, ["clutch_code","clutch_genotype","cross_date","cross_code"])
fallback = [c for c in grid.columns if c not in primary and c != sel_col]
display_cols = [sel_col] + primary + fallback

ro = st.data_editor(
    grid[display_cols],
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        sel_col:                          st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code":                    st.column_config.TextColumn("Clutch code", disabled=True),
        "clutch_genotype":                st.column_config.TextColumn("Clutch genotype", disabled=True, width="large"),
        "clutch_fusions":                 st.column_config.TextColumn("Clutch fusions", disabled=True),
        "clutch_fluors":                  st.column_config.TextColumn("Clutch fluors", disabled=True),
        "cross_date":                     st.column_config.DateColumn("Cross date", disabled=True, format="YYYY-MM-DD"),
        "cross_code":                     st.column_config.TextColumn("Cross code", disabled=True),
        "tank_pair_code":                 st.column_config.TextColumn("TP code", disabled=True),
        "mom_fish_code":                  st.column_config.TextColumn("Mom FSH", disabled=True),
        "dad_fish_code":                  st.column_config.TextColumn("Dad FSH", disabled=True),
        "mom_tank_code":                  st.column_config.TextColumn("Mom tank", disabled=True),
        "dad_tank_code":                  st.column_config.TextColumn("Dad tank", disabled=True),
        "mom_genotype":                   st.column_config.TextColumn("Mom genotype", disabled=True, width="large"),
        "dad_genotype":                   st.column_config.TextColumn("Dad genotype", disabled=True, width="large"),
        "clutch_created_at":              st.column_config.DatetimeColumn("Clutch created", disabled=True),
        "cross_created_at":               st.column_config.DatetimeColumn("Cross created", disabled=True),
    },
    key="v_clutches_overview_grid",
)
mask = ro.get(sel_col, pd.Series(False, index=ro.index)).fillna(False).astype(bool)
picked = ro[mask]

# ── Details split into 3 stacked tables ──────────────────────────────────────
st.divider()
st.subheader("Details")

if len(picked) == 0:
    st.info("Select a single row above to view details.")
elif len(picked) > 1:
    st.warning("Multiple rows selected. Please select just one to view details.")
else:
    sel = picked.iloc[0].to_dict()

    def _pivot(title: str, rows: list[tuple[str, Any]]):
        dfp = pd.DataFrame(rows, columns=["Field","Value"])
        st.subheader(title)
        st.dataframe(dfp, hide_index=True, use_container_width=True)

    # Mother profile (all v_fish_overview fields we expect)
    mom_rows = [
        ("Fish code",               sel.get("mom_fish_code")),
        ("Tank code",               sel.get("mom_tank_code")),
        ("Nickname",                sel.get("mom_nickname")),
        ("Genetic background",      sel.get("mom_genetic_background")),
        ("Line building stage",     sel.get("mom_line_building_stage")),
        ("Birthday",                sel.get("mom_birthday")),
        ("Genotype",                sel.get("mom_genotype")),
        ("Fusions",                 sel.get("mom_fusions")),
        ("Fluors",                  sel.get("mom_fluors")),
        ("Fusion location (tags)",  sel.get("mom_tags")),
        ("Markers",                 sel.get("mom_markers")),
        ("n_fusions",               sel.get("mom_n_fusions")),
        ("Dyes",                    sel.get("mom_dyes")),
        ("Profile created",         sel.get("mom_profile_created_at")),
    ]
    _pivot("Mother — profile", mom_rows)

    # Father profile
    dad_rows = [
        ("Fish code",               sel.get("dad_fish_code")),
        ("Tank code",               sel.get("dad_tank_code")),
        ("Nickname",                sel.get("dad_nickname")),
        ("Genetic background",      sel.get("dad_genetic_background")),
        ("Line building stage",     sel.get("dad_line_building_stage")),
        ("Birthday",                sel.get("dad_birthday")),
        ("Genotype",                sel.get("dad_genotype")),
        ("Fusions",                 sel.get("dad_fusions")),
        ("Fluors",                  sel.get("dad_fluors")),
        ("Fusion location (tags)",  sel.get("dad_tags")),
        ("Markers",                 sel.get("dad_markers")),
        ("n_fusions",               sel.get("dad_n_fusions")),
        ("Dyes",                    sel.get("dad_dyes")),
        ("Profile created",         sel.get("dad_profile_created_at")),
    ]
    _pivot("Father — profile", dad_rows)

    # Clutch / Cross — metadata
    clutch_rows = [
        ("Cross code",          sel.get("cross_code")),
        ("Cross date",          sel.get("cross_date")),
        ("Cross created",       sel.get("cross_created_at")),
        ("Tank pair code",      sel.get("tank_pair_code")),
        ("Clutch code (this row)", sel.get("clutch_code")),
        ("Clutch genotype",     sel.get("clutch_genotype")),
        ("Expected fusions",    sel.get("expected_fusions")),
        ("Expected fluors",     sel.get("expected_fluors")),
        ("Applied fusions",     sel.get("clutch_fusions")),
        ("Applied fluors",      sel.get("clutch_fluors")),
        ("Clutch created",      sel.get("clutch_created_at")),
    ]
    _pivot("Clutch / Cross — metadata", clutch_rows)

# Done. All data comes straight from public.v_clutches_overview