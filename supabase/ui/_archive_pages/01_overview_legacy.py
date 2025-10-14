# supabase/ui/pages/01_🔎_overview.py
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

import pandas as pd
import streamlit as st
from sqlalchemy import text

from supabase.ui.lib.app_ctx import get_engine, engine_info
from carp_app.lib.queries import load_fish_overview

PAGE_TITLE = "CARP — Overview"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🔎", layout="wide")
st.title("🔎 Overview")

eng = get_engine()
dbg = engine_info(eng)
st.caption(f"DB debug → db={dbg['db']} user={dbg['usr']} host={dbg['host']}:{dbg['port']}")

# If DB is empty, say it explicitly and stop
with eng.begin() as cx:
    fish_rows = cx.execute(text("select count(*) from public.fish")).scalar()
if fish_rows == 0:
    st.info("Database is empty. Use **📤 New fish from CSV** to import.")
    st.stop()

# Controls
c1, c2 = st.columns([3, 1])
with c1:
    q = st.text_input("Search (code, name, genotype, created_by, batch, nickname)", "")
with c2:
    lim = st.number_input("Row limit", min_value=10, max_value=5000, value=1000, step=10)

# Load overview; if the view schema is out-of-sync, fall back gracefully
try:
    df = load_fish_overview(eng, q=q, limit=int(lim))
except Exception as e:
    st.warning(f"Overview view had an issue ({e.__class__.__name__}); showing base view instead.")
    with eng.begin() as cx:
        df = pd.read_sql_query(
            """
            select id, fish_code, name,
                   transgene_base_code_filled as transgene_base_code,
                   allele_code_filled as allele_code,
                   allele_name_filled as allele_name,
                   created_at, created_by
            from public.v_fish_overview
            order by created_at desc
            limit %(lim)s
            """,
            con=cx.connection,
            params={"lim": int(lim)},
        )

if df.empty:
    st.info("No rows match the current filters.")
else:
    cols = [
        "fish_code","name",
        "transgene_base_code","allele_code","allele_name",
        "line_building_stage",
        "date_birth","age_weeks",
        "plasmid_injections_text","rna_injections_text",
        "batch_label","created_by","created_at","id",
    ]
    show = [c for c in cols if c in df.columns]
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
    if "age_weeks" in df.columns:
        df["age_weeks"] = pd.to_numeric(df["age_weeks"], errors="coerce").astype("Int64")
    st.dataframe(df[show], width='stretch')
    st.caption("Source: public.vw_fish_overview_with_label (fallback to v_fish_overview on errors).")