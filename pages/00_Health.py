# pages/00_Health.py

import os
import json
import streamlit as st
from typing import Optional
from lib.authz import require_app_access, read_only_banner, logout_button
from lib.db import get_engine, fetch_df  # <-- import fetch_df

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

def _test_dsn(dsn_label: str, dsn_value: Optional[str]):
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

st.divider()
st.subheader("Audit")

with st.expander("View recent audit events", expanded=False):
    if st.button("Load recent audit events"):
        pool_dsn = st.secrets.get("CONN_POOL") or st.secrets.get("CONN_DIRECT")
        if not pool_dsn:
            st.warning("No CONN_POOL/CONN_DIRECT found in secrets.")
        else:
            try:
                engine = get_engine(pool_dsn)  # <-- define engine here
                with engine.connect() as cx:
                    df_audit = fetch_df(
                        cx,
                        """
                        select happened_at, actor, action, details
                        from public.audit_events
                        order by happened_at desc
                        limit 20
                        """
                    )
                if not df_audit.empty:
                    st.dataframe(df_audit, use_container_width=True)
                else:
                    st.caption("No audit events recorded yet.")
            except Exception as e:
                st.error("Failed to load audit events.")
                st.exception(e)


# -- add to imports at top if missing --
from lib.db import get_engine, fetch_df, exec_sql
from lib.audit import log_event

# ... keep the rest of your Health page as-is ...

# --- Audit: writer + viewer (use POOL DSN consistently) ---
pool_dsn = st.secrets.get("CONN_POOL")
engine = get_engine(pool_dsn) if pool_dsn else None

st.divider()
st.subheader("Audit")

colW, colR = st.columns([1, 1])

with colW:
    if st.button("Write test audit event"):
        if not engine:
            st.error("No CONN_POOL configured.")
        else:
            try:
                with engine.begin() as cx:
                    # actor/action/details are free-form; keep it simple
                    log_event(cx, "health_smoke_test", {"note": "manual test from Health page"})
                st.success("Wrote test audit event.")
            except Exception as e:
                st.error(f"Failed to write audit event: {e}")

with colR:
    if st.button("Refresh audit list"):
        st.rerun()

# Always show latest 20
if engine:
    try:
        with engine.connect() as cx:
            df_audit = fetch_df(
                cx,
                """
                select happened_at, actor, action, details
                from public.audit_events
                order by happened_at desc
                limit 20
                """
            )
        if not df_audit.empty:
            st.dataframe(df_audit, use_container_width=True)
        else:
            st.caption("No audit events recorded yet.")
    except Exception as e:
        st.error("Could not load audit events.")
        st.exception(e)
else:
    st.caption("No engine available for audit display.")