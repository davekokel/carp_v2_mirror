# pages/00_Health.py
import streamlit as st
from lib.authz import require_app_access, read_only_banner, logout_button

# Gate + banners (no DB work here)
require_app_access("🔐 CARP — Private")
read_only_banner()
logout_button("sidebar")  # visible even if DB is down

st.set_page_config(page_title="Health", layout="wide")
st.title("Health")

# Basic UI-only diagnostics (no DB access)
col1, col2 = st.columns(2)
with col1:
    st.success("✅ UI is rendering")
    st.write("ENV:", st.secrets.get("ENV_NAME", "(unset)"))
    st.write("READ_ONLY:", st.secrets.get("READ_ONLY", "(unset)"))
with col2:
    st.write("Has CONN_POOL:", bool(st.secrets.get("CONN_POOL")))
    st.write("Has CONN_DIRECT:", bool(st.secrets.get("CONN_DIRECT")))
    st.caption("This page does not connect to the database.")

st.divider()

# Optional, *safe* on-demand DB check behind a button (wrapped in try/except)
with st.expander("On-demand DB check (optional)"):
    if st.button("Test DB connection"):
        try:
            from lib.db import get_engine
            engine = get_engine()  # builds engine from secrets; may still fail
            with engine.connect() as cx:
                cx.exec_driver_sql("SELECT 1")
            st.success("DB connection OK (SELECT 1)")
        except Exception as e:
            st.error(f"DB connection failed: {e}")
            st.caption("This failure will not crash the app.")