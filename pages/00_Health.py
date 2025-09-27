# pages/00_Health.py

import os
import streamlit as st
from lib.authz import require_app_access, read_only_banner, logout_button
from lib.db import get_engine

st.set_page_config(page_title="CARP — Health", layout="wide")

# Gate + banner + logout
require_app_access("🔐 CARP — Private")
read_only_banner()
logout_button("sidebar")

st.title("Health")

# Environment info (no DB access here)
env_name = st.secrets.get("ENV_NAME", "(unset)")
read_only = st.secrets.get("READ_ONLY", False)
timeout = st.secrets.get("TIMEOUT_MINUTES", 0)
audit = st.secrets.get("AUDIT_ENABLED", False)

colA, colB, colC, colD = st.columns(4)
colA.metric("ENV_NAME", str(env_name))
colB.metric("READ_ONLY", str(read_only))
colC.metric("TIMEOUT_MINUTES", str(timeout))
colD.metric("AUDIT_ENABLED", str(audit))

st.divider()
st.subheader("Database connectivity (manual tests)")

def _test_dsn(dsn_label: str, dsn_value: str | None):
    if not dsn_value:
        st.warning(f"{dsn_label}: not set in secrets.")
        return
    try:
        engine = get_engine(dsn_value)
        with engine.connect() as cx:
            cx.exec_driver_sql("select 1")
        st.success(f"{dsn_label}: ✅ OK")
    except Exception as e:
        st.error(f"{dsn_label}: ❌ Failed")
        st.exception(e)

left, right = st.columns(2)
with left:
    if st.button("Test POOL connection"):
        _test_dsn("CONN_POOL", st.secrets.get("CONN_POOL"))

with right:
    if st.button("Test DIRECT connection"):
        _test_dsn("CONN_DIRECT", st.secrets.get("CONN_DIRECT"))

st.caption("These tests only run when you press the button, so the page won’t crash if the DB is unreachable.")