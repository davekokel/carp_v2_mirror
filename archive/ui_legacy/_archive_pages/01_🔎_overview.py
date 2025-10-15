from __future__ import annotations

import os
from typing import List

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

PAGE_TITLE = "CARP — Overview"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🔎")

ENGINE = None
def _get_engine():
    global ENGINE
    if ENGINE is not None:
        return ENGINE
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL is not set")
    ENGINE = create_engine(url, future=True)
    return ENGINE

def _query_overview(q: str, stages: List[str], limit: int) -> pd.DataFrame:
    # Build a stable "search haystack" from the label view
    sql = """
    with base as (
      select
        fish_code,
        name,
        nickname,
        coalesce(line_building_stage, line_building_stage_print) as stage_text,
        date_birth,
        coalesce(genetic_background, genetic_background_print) as background_text,
        genotype_print as genotype_text,
        created_at,
        age_days
      from public.vw_fish_overview_with_label
    )
    select * from base
    """
    where, params = [], {}

    # Tokenize query (AND semantics, quotes, -negation)
    import shlex
    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]

    # Auto-detect stage tokens (F0/F1/F2/founder) from the free-text box
    STAGE_VALUES = {"FOUNDER","F0","F1","F2","F3","F4"}
    auto_stages, normal = [], []
    for t in tokens:
        neg = t.startswith("-")
        core = t[1:] if neg else t
        if not neg and core.upper() in STAGE_VALUES:
            auto_stages.append(core.upper())
        else:
            normal.append(t)

    # Build haystack once
    haystack = "concat_ws(' ', coalesce(fish_code,''), coalesce(name,''), coalesce(nickname,''), coalesce(genotype_text,''), coalesce(background_text,''), coalesce(stage_text,''))"

    # Text terms → AND across haystack
    for i, tok in enumerate(normal):
        key = f"t{i}"
        if tok.startswith("-"):
            params[key] = f"%{tok[1:]}%"
            where.append(f"NOT ({haystack} ILIKE :{key})")
        else:
            params[key] = f"%{tok}%"
            where.append(f"({haystack} ILIKE :{key})")

    # Merge stage filters from pill + auto-detected tokens
    stage_filters = [s.upper() for s in stages] if stages else []
    for s in auto_stages:
        if s not in stage_filters:
            stage_filters.append(s)
    if stage_filters:
        where.append("upper(stage_text) = ANY(:stages)")
        params["stages"] = stage_filters

    if where:
        sql += "\nWHERE " + "\n  AND ".join(where)
    sql += "\nORDER BY created_at DESC\nLIMIT :lim"
    params["lim"] = int(limit)

    with _get_engine().begin() as cx:
        return pd.read_sql(text(sql), cx, params=params)

def main():
    st.title("🔎 Overview")
    with st.form("filters"):
        c1, c2, c3 = st.columns([2,2,1])
        with c1:
            q = st.text_input("Search (code / name / nickname / genotype / background)", "")
        with c2:
            try:
                stages_df = pd.read_sql(
                    text("select distinct upper(coalesce(line_building_stage, line_building_stage_print)) as s from public.vw_fish_overview_with_label where coalesce(line_building_stage, line_building_stage_print) is not null order by 1"),
                    _get_engine()
                )
                stage_choices = [s for s in stages_df["s"].astype(str).tolist() if s]
            except Exception:
                stage_choices = []
            stages = st.multiselect("Stage", stage_choices, default=[])
        with c3:
            limit = st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100)
        submitted = st.form_submit_button("Apply")

    df = _query_overview(q, stages, int(limit))
    st.caption(f"{len(df)} rows")

    view = df.rename(columns={
        "line_building_stage": "stage",
        "genetic_background": "genetic_background",
        "genotype_text": "genotype",
    })[[
        "fish_code", "name", "nickname", "genotype",
        "genetic_background", "stage", "date_birth", "age_days", "created_at"
    ]]

    st.dataframe(view, width="stretch", hide_index=True)

if __name__ == "__main__":
    main()