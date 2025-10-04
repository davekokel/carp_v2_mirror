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

PAGE_TITLE = "CARP — Overview"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🔎", layout="wide")
st.title("🔎 Overview")

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
        for k in list(st.session_state.keys()):
            if k in ("overview_grid", "overview_grid_v2"):
                st.session_state.pop(k, None)
        st.rerun()

# ---- Filters / search
with st.expander("Filters", expanded=True):
    q = st.text_input("Search (code, name, genotype, created_by, batch, nickname)", value="").strip()
    limit = st.number_input("Row limit", min_value=50, max_value=10000, value=1000, step=50)

# ---- Load + render (final) ----
def _load_overview(engine, q: str, limit: int) -> pd.DataFrame:
    # clamp limit
    try:
        lim = int(limit)
    except Exception:
        lim = 1000
    lim = max(1, min(lim, 10000))

    # detect if the label view has 'date_birth'
    with engine.begin() as cx:
        has_dob = cx.execute(text("""
            select exists (
              select 1
              from information_schema.columns
              where table_schema='public'
                and table_name='vw_fish_overview_with_label'
                and column_name='date_birth'
            )
        """)).scalar()

    params: Dict[str, Any] = {}
    where: List[str] = []
    if q:
        params["p"] = f"%{q}%"
        where.append("""
        (
          b.fish_code ilike :p
          or coalesce(b.name,'') ilike :p
          or coalesce(b.transgene_base_code_filled,'') ilike :p
          or coalesce(b.allele_code_filled,'') ilike :p
          or coalesce(b.created_by,'') ilike :p
          or coalesce(w.created_by_enriched,'') ilike :p
          or coalesce(w.batch_label,'') ilike :p
          or coalesce(w.nickname,'') ilike :p
          or coalesce(w.line_building_stage,'') ilike :p
        )
        """)
    where_sql = (" where " + " and ".join(where)) if where else ""

    dob_expr = "w.date_birth" if has_dob else "null::date as date_birth"

    sql_txt = text(f"""
      select
        b.id,
        b.fish_code,
        b.name,
        (case
           when b.transgene_base_code_filled is not null and b.allele_code_filled is not null
           then b.transgene_base_code_filled || ' : ' || b.allele_code_filled
           else null
         end) as transgene_pretty,
        b.transgene_base_code_filled,
        b.allele_code_filled,
        b.allele_name_filled,
        b.created_by,
        b.created_at,
        w.batch_label,
        w.created_by_enriched,
        w.nickname,
        w.line_building_stage,
        {dob_expr},
        w.last_plasmid_injection_at,
        w.plasmid_injections_text,
        w.last_rna_injection_at,
        w.rna_injections_text
      from public.v_fish_overview b
      left join public.vw_fish_overview_with_label w
        on w.fish_code = b.fish_code
      {where_sql}
      order by b.created_at desc
      limit {lim}
    """)
    return pd.read_sql(sql_txt, engine, params=params)

# actually load + render
df = _load_overview(eng, q=q, limit=limit)

if df.empty:
    st.info("No rows match the current filters. (Cohorts appear here after genotype is linked.)")
else:
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)

    preferred = [
        "fish_code", "name", "transgene_pretty",
        "transgene_base_code_filled", "allele_code_filled", "allele_name_filled",
        "nickname", "line_building_stage", "date_birth",
        "batch_label",
        "created_by_enriched", "created_by", "created_at",
        "last_plasmid_injection_at", "plasmid_injections_text",
        "last_rna_injection_at", "rna_injections_text",
        "id",
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
            "transgene_pretty": st.column_config.TextColumn("Genotype (base : allele)"),
            "transgene_base_code_filled": st.column_config.TextColumn("Transgene base codes"),
            "allele_code_filled": st.column_config.TextColumn("Allele numbers"),
            "allele_name_filled": st.column_config.TextColumn("Allele names"),
            "nickname": st.column_config.TextColumn("Nickname"),
            "line_building_stage": st.column_config.TextColumn("Line stage"),
            "date_birth": st.column_config.DateColumn("Birth date"),
            "batch_label": st.column_config.TextColumn("Batch label"),
            "created_by": st.column_config.TextColumn("Created by"),
            "created_by_enriched": st.column_config.TextColumn("Created by (enriched)"),
            "created_at": st.column_config.DatetimeColumn("Created"),
            "last_plasmid_injection_at": st.column_config.DatetimeColumn("Last DNA injection"),
            "plasmid_injections_text": st.column_config.TextColumn("Injected DNA (plasmid)"),
            "last_rna_injection_at": st.column_config.DatetimeColumn("Last RNA injection"),
            "rna_injections_text": st.column_config.TextColumn("Injected RNA"),
            "id": st.column_config.TextColumn("ID"),
        },
        disabled=True,
    )

st.caption(
    "This page uses base `v_fish_overview` for core fields (id, name, genotype) "
    "and LEFT JOINs `vw_fish_overview_with_label` for extras (batch, nickname, stage, DOB, injections)."
)