# supabase/ui/pages/02_🔎_overview.py
from __future__ import annotations

# --- sys.path before local imports ---
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]  # …/carp_v2
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from sqlalchemy import text
from typing import Dict, Any, List

# Shared engine (centralized on Home)
from supabase.ui.lib_shared import current_engine, connection_info

# 🔒 auth
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

PAGE_TITLE = "CARP — Overview Labels"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🔎", layout="wide")
st.title("🔎 Overview Labels")

# ---- Use centralized engine; show DB info
eng = current_engine()
dbg = connection_info(eng)
st.caption(f"DB debug → db={dbg['db']} user={dbg['user']}")

# ---- Force-refresh (clear caches + editor state) ----
colR1, colR2 = st.columns([1, 4])
with colR1:
    if st.button("🔁 Refresh data"):
        try:
            st.cache_data.clear()
        except Exception:
            pass
        try:
            st.cache_resource.clear()
        except Exception:
            pass
        # Clear common editor keys so stale state doesn't bleed through
        for k in list(st.session_state.keys()):
            if k in ("overview_grid", "overview_grid_v2", "parent_picker", "parent_picker_nc"):
                st.session_state.pop(k, None)
        st.rerun()

# ---- Filters / search
with st.expander("Filters", expanded=True):
    # v_fish_overview already excludes no-genotype rows; toggle kept for safety (no-op now)
    hide_no_genotype = st.checkbox("Hide rows with no genotype links", value=True)
    q = st.text_input("Search (code, name, genotype, created_by)", value="").strip()
    limit = st.number_input("Row limit", min_value=50, max_value=10000, value=1000, step=50)

# ---- SQL loader (no caching: always reflect DB)
def _load_overview(engine, q: str, hide_no_genotype: bool, limit: int) -> pd.DataFrame:
    # clamp limit to a sane integer
    try:
        lim = int(limit)
    except Exception:
        lim = 1000
    lim = max(1, min(lim, 10000))

    where: List[str] = []
    params: Dict[str, Any] = {}

    # This is effectively a no-op because v_fish_overview excludes orphans,
    # but kept for future safety if the view changes.
    if hide_no_genotype:
        where.append("""
          (coalesce(transgene_base_code_filled,'') <> ''
           or coalesce(allele_code_filled,'') <> '')
        """)

    if q:
        params["p"] = f"%{q}%"
        where.append("""
          (
            fish_code ilike :p
            or coalesce(name,'') ilike :p
            or coalesce(transgene_base_code_filled,'') ilike :p
            or coalesce(allele_code_filled,'') ilike :p
            or coalesce(created_by,'') ilike :p
          )
        """)

    where_sql = (" where " + " and ".join(where)) if where else ""
    sql_txt = text(f"""
        select
          id,
          fish_code,
          name,
          transgene_base_code_filled,
          allele_code_filled,
          allele_name_filled,
          created_by,
          created_at
        from public.v_fish_overview
        {where_sql}
        order by created_at desc
        limit {lim}
    """)
    return pd.read_sql(sql_txt, engine, params=params)

# ---- Load + render
df = _load_overview(eng, q=q, hide_no_genotype=hide_no_genotype, limit=limit)

if df.empty:
    st.info("No rows match the current filters.")
else:
    # Nice types for display
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
    # Reorder a bit for readability
    preferred = [
        "fish_code", "name",
        "transgene_base_code_filled", "allele_code_filled", "allele_name_filled",
        "created_by", "created_at", "id",
    ]
    cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    df = df[cols]

    st.data_editor(
        df,
        key="overview_grid_v2",
        width="stretch",
        hide_index=True,
        column_config={
            "fish_code": st.column_config.TextColumn("Fish code"),
            "name": st.column_config.TextColumn("Name"),
            "transgene_base_code_filled": st.column_config.TextColumn("Transgene base codes"),
            "allele_code_filled": st.column_config.TextColumn("Allele numbers"),
            "allele_name_filled": st.column_config.TextColumn("Allele names"),
            "created_by": st.column_config.TextColumn("Created by"),
            "created_at": st.column_config.DatetimeColumn("Created"),
            "id": st.column_config.TextColumn("ID"),
        },
        disabled=True,   # viewer mode
    )

st.caption("This page reads from public.v_fish_overview only (no LEFT JOINs), so it matches the canonical cohort set.")