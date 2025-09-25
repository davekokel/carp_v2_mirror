# streamlit_app.py
import streamlit as st

st.set_page_config(page_title="CARP", layout="wide")
st.title("CARP")
st.caption("Use the sidebar to navigate pages.")

# show a tiny secrets sanity panel (never blocks)
def _has_secret(k: str) -> str:
    try:
        v = st.secrets.get(k)
        return "yes" if (isinstance(v, str) and v.strip()) else ("yes" if v else "no")
    except Exception:
        return "no"

c1, c2, c3 = st.columns(3)
with c1: st.metric("ENV_NAME", st.secrets.get("ENV_NAME", "(unset)"))
with c2: st.metric("Has CONN", _has_secret("CONN"))
with c3: st.metric("Has PGHOST", _has_secret("PGHOST"))

st.divider()
st.subheader("Pages")
st.page_link("pages/01_Overview.py", label="Overview", icon="📊")
st.page_link("pages/02_Assign_and_Labels.py", label="Assign & Labels", icon="🏷️")
st.page_link("pages/02_Details.py", label="Details", icon="🧬")
st.page_link("pages/09_seed_loader.py", label="Seed Loader", icon="📦")

# Optional: DB check on demand (prevents blocking at startup)
if st.button("Run DB check"):
    try:
        from lib.db import get_engine, quick_db_check
        eng = get_engine()  # reads st.secrets
        st.success(quick_db_check(eng))
    except Exception as e:
        st.error(f"DB check failed: {e}")