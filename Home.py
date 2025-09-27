# supabase/ui/Home.py
import streamlit as st
from sqlalchemy import text

from lib_shared import pick_environment
from lib.db import get_engine, quick_db_check

from lib.authz import require_app_access
require_app_access("🔐 CARP — Private")

st.caption(f"secrets seen → CONN:{bool(st.secrets.get('CONN'))} "
           f"PGHOST:{bool(st.secrets.get('PGHOST'))} "
           f"ENV_NAME:{st.secrets.get('ENV_NAME','(missing)')}")

st.set_page_config(page_title="CARP — Home", layout="wide")
st.title("CARP Dashboard")

# Show where we're pointed
env, label = pick_environment()
st.caption(f"Environment: **{label}**")


# Build engine from PG* secrets (db.py handles URL)
engine = get_engine()

# Quick connectivity check
status = quick_db_check(engine)
if status.startswith("OK:"):
    st.success(status)
else:
    st.error(status)

st.divider()

# A tiny “recent counts” panel so you can sanity check quickly
with engine.connect() as cx:
    rows = cx.execute(text("""
        select 'fish' as k, count(*) as v from public.fish
        union all select 'transgenes', count(*) from public.transgenes
        union all select 'allele_catalog', count(*) from public.transgene_allele_catalog
        union all select 'fish_transgene_alleles', count(*) from public.fish_transgene_alleles
        union all select 'tank_assignments', count(*) from public.tank_assignments
        union all select 'overview_view', count(*) from public.v_fish_overview_v1
    """)).fetchall()

st.subheader("Quick counts")
st.table(rows)

st.info("Use the pages in the sidebar (Overview, Assign & Labels, Seed Loader).")