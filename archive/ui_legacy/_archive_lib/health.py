from __future__ import annotations
# supabase/ui/health.py
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
            st.dataframe(checks["counts"], width='stretch')

        if "overview_preview" in checks:
            with st.expander("Overview preview (first 20)"):
                df = checks["overview_preview"].copy()
                # stringify UUID-like id columns so Arrow is happy
                for _c in list(df.columns):
                    if _c.lower().endswith('id'):
                        try:
                            df[_c] = df[_c].astype(str)
                        except Exception:
                            pass
                st.dataframe(df, width='stretch')

# --- Local snapshot (pg_dump) -------------------------------------------------
def render_snapshot_button():
    import os, subprocess, datetime, streamlit as st
    host = os.getenv("PGHOST", st.secrets.get("PGHOST","127.0.0.1"))
    port = str(os.getenv("PGPORT", st.secrets.get("PGPORT", 54322)))
    user = os.getenv("PGUSER", st.secrets.get("PGUSER","postgres"))
    db   = os.getenv("PGDATABASE", st.secrets.get("PGDATABASE","postgres"))
    pw   = os.getenv("PGPASSWORD", st.secrets.get("PGPASSWORD","postgres"))

    snaps = os.path.expanduser("~/Documents/github/carp_v2/snapshots/snapshots_local")
    os.makedirs(snaps, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = f"{snaps}/local_full_{ts}.dump"

    st.subheader("Snapshot")
    st.caption(f"Dest: {out}")
    if st.button("Create DB snapshot (.dump)"):
        env = dict(os.environ)
        env["PGPASSWORD"] = str(pw)
        cmd = ["pg_dump","-Fc","-h",host,"-p",str(port),"-U",user,"-d",db,"-f",out]
        try:
            subprocess.check_call(cmd, env=env)
            st.success(f"Snapshot created: {out}")
        except Exception as e:
            st.error(f"Snapshot failed: {e}")


# --- Seed kit loader (local) --------------------------------------------------
def render_seed_loader():
    import os, subprocess, streamlit as st
    st.subheader("Seed kit loader (local)")
    repo_root = os.path.expanduser("~/Documents/github/carp_v2")
    script = f"{repo_root}/scripts/load_seedkit_core_local.sh"
    st.caption(script)
    if st.button("Load seed kit now"):
        try:
            subprocess.check_call(["bash", script], cwd=repo_root)
            st.success("Seed kit loaded.")
        except Exception as e:
            st.error(f"Seed load failed: {e}")
