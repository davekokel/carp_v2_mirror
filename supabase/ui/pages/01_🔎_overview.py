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
    sql = """
    with base as (
      select
        fish_code,
        name,
        nickname,
        line_building_stage,
        date_birth,
        genetic_background,
        created_at,
        genotype_text,
        age_days
      from public.v_fish_overview
    )
    select * from base
    """
    where, params = [], {}
    if q:
        where.append("""(
          fish_code ilike :q OR
          coalesce(nickname,'') ilike :q OR
          coalesce(name,'') ilike :q OR
          coalesce(genotype_text,'') ilike :q OR
          coalesce(genetic_background,'') ilike :q
        )""")
        params["q"] = f"%{q}%"
    if stages:
        where.append("coalesce(line_building_stage,'') = ANY(:stages)")
        params["stages"] = stages
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
                    text("select distinct line_building_stage from public.v_fish_overview order by 1"),
                    _get_engine()
                )
                stage_choices = [s for s in stages_df["line_building_stage"].dropna().astype(str).tolist() if s]
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