# supabase/ui/health.py
from __future__ import annotations
import streamlit as st
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

def _fetch_df(engine: Engine, sql: str) -> pd.DataFrame:
    with engine.connect() as cx:
        return pd.read_sql(text(sql), cx)

def compute_invariants(engine: Engine) -> dict:
    """Return a dict of DataFrames (and small stats) for quick health checks."""
    results: dict[str, pd.DataFrame | int | str] = {}

    # A) Row counts across key tables
    results["counts"] = _fetch_df(engine, """
      select 'fish'        as table, count(*)::bigint as n from public.fish
      union all select 'alleles',    count(*)         from public.transgene_alleles
      union all select 'links',      count(*)         from public.fish_transgene_alleles
      union all select 'treatments', count(*)         from public.treatments
      union all select 'tanks',      count(*)         from public.tanks
      order by 1;
    """)

    # B) Blank fish names
    results["blank_names"] = _fetch_df(engine, """
      select count(*)::bigint as blank_names
      from public.fish
      where nullif(trim(name),'') is null;
    """)

    # C) Fish rows with no allele links
    results["fish_missing_links"] = _fetch_df(engine, """
      select count(*)::bigint as fish_missing_links
      from public.fish f
      left join public.fish_transgene_alleles l
        on l.fish_id = f.id
      where l.fish_id is null;
    """)

    # D) Duplicate allele numbers per transgene (should be unique per base_code)
    results["dup_alleles_per_transgene"] = _fetch_df(engine, """
      with d as (
        select transgene_base_code, allele_number, count(*) as c
        from public.transgene_alleles
        group by 1,2
        having count(*) > 1
      )
      select count(*)::bigint as dup_pairs from d;
    """)

    # E) Overview view exists & sample rows (optional preview)
    try:
        results["overview_preview"] = _fetch_df(engine, """
          select *
          from public.v_fish_overview_v1
          order by fish_name nulls last
          limit 20;
        """)
    except Exception as _:
        # View may not exist yet; that’s fine.
        pass

    return results

def render_health_panel(engine: Engine) -> None:
    checks = compute_invariants(engine)

    with st.sidebar:
        st.subheader("DB Health")
        # Small KPI row
        kpi = checks["counts"].set_index("table")["n"].to_dict()
        col1, col2, col3 = st.columns(3)
        col1.metric("Fish", kpi.get("fish", 0))
        col2.metric("Alleles", kpi.get("alleles", 0))
        col3.metric("Links", kpi.get("links", 0))

        # Problem counts
        blanks = int(checks["blank_names"]["blank_names"].iloc[0])
        missing = int(checks["fish_missing_links"]["fish_missing_links"].iloc[0])
        dups = int(checks["dup_alleles_per_transgene"]["dup_pairs"].iloc[0])

        st.caption(f"Blank fish names: **{blanks}**")
        st.caption(f"Fish missing links: **{missing}**")
        st.caption(f"Dup allele# per transgene: **{dups}**")

        # Details expanders
        with st.expander("Counts (tables)"):
            st.dataframe(checks["counts"], use_container_width=True)

        if "overview_preview" in checks:
            with st.expander("Overview preview (first 20)"):
                st.dataframe(checks["overview_preview"], use_container_width=True)