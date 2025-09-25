# streamlit_app.py
import streamlit as st
from typing import Optional

st.set_page_config(page_title="CARP", layout="wide")

# Optional: quick status panel
def secret_bool(k: str) -> bool:
    try:
        return bool(st.secrets.get(k))
    except Exception:
        return False

st.title("CARP")
st.caption("Use the sidebar to navigate pages.")

# Show env + secrets presence
env_name: Optional[str] = None
try:
    env_name = st.secrets.get("ENV_NAME")
except Exception:
    env_name = None

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("ENV_NAME", env_name or "(unset)")
with c2:
    st.metric("Has CONN", "yes" if secret_bool("CONN") else "no")
with c3:
    st.metric("Has PGHOST", "yes" if secret_bool("PGHOST") else "no")

# Optional DB check (works whether you set CONN or PG* parts)
try:
    from lib.db import get_engine, quick_db_check  # present in your repo
    eng = get_engine()  # reads st.secrets
    st.success(quick_db_check(eng))
except Exception as e:
    st.info(f"DB check skipped/failed: {e}")

st.subheader("Pages")
st.page_link("pages/01_Overview.py", label="Overview", icon="📊")
st.page_link("pages/02_Assign_and_Labels.py", label="Assign & Labels", icon="🏷️")
st.page_link("pages/02_Details.py", label="Details", icon="🧬")
st.page_link("pages/09_seed_loader.py", label="Seed Loader", icon="📦")