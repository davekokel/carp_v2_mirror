# pages/00_Health.py

import os
import time
import streamlit as st

from lib.authz import require_app_access, read_only_banner, logout_button
from lib.db import get_engine, fetch_df, exec_sql

st.set_page_config(page_title="CARP — Health", layout="wide")

# ---------------- Gate + banner + logout ----------------
require_app_access("🔐 CARP — Private")
read_only_banner()
logout_button("sidebar")

st.title("Health")

# ---------------- Basics (no DB here) ----------------
env_name = st.secrets.get("ENV_NAME", "(unset)")
read_only = st.secrets.get("READ_ONLY", False)
timeout = st.secrets.get("TIMEOUT_MINUTES", 0)
audit_enabled = st.secrets.get("AUDIT_ENABLED", False)

colA, colB, colC, colD = st.columns(4)
colA.metric("ENV_NAME", str(env_name))
colB.metric("READ_ONLY", str(read_only))
colC.metric("TIMEOUT_MINUTES", str(timeout))
colD.metric("AUDIT_ENABLED", str(audit_enabled))

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
    if st.button("Test POOL connection", key="btn_test_pool"):
        _test_dsn("CONN_POOL", st.secrets.get("CONN_POOL"))

with right:
    if st.button("Test DIRECT connection", key="btn_test_direct"):
        _test_dsn("CONN_DIRECT", st.secrets.get("CONN_DIRECT"))

st.caption("These tests only run when you press the button, so the page won’t crash if the DB is unreachable.")

st.divider()
st.subheader("Audit events")

# --------------- Helpers -----------------
def _write_test_audit(cx):
    # Minimal no-op test event
    exec_sql(
        cx,
        """
        insert into public.audit_events (happened_at, actor, action, details)
        values (now(), 'health_page', 'test_event', '{"note":"manual test"}'::jsonb)
        """,
    )

def _fetch_audit_df(cx):
    return fetch_df(
        cx,
        """
        select happened_at, actor, action, details
        from public.audit_events
        order by happened_at desc
        limit 50
        """
    )

# Session keys to avoid duplicate widget IDs and to drive rerenders
if "audit_refresh_counter" not in st.session_state:
    st.session_state.audit_refresh_counter = 0

if "audit_last_write_ts" not in st.session_state:
    st.session_state.audit_last_write_ts = 0.0

pool_dsn = st.secrets.get("CONN_POOL") or st.secrets.get("CONN_DIRECT")
engine = get_engine(pool_dsn) if pool_dsn else None

controls_col, table_col = st.columns([1, 3])

with controls_col:
    write_clicked = st.button("Write test audit event", key="btn_audit_write", disabled=not bool(engine))
    refresh_clicked = st.button("Refresh audit list", key=f"btn_audit_refresh_{st.session_state.audit_refresh_counter}", disabled=not bool(engine))

with table_col:
    if not engine:
        st.warning("No DB connection string set (CONN_POOL / CONN_DIRECT).")
    else:
        # Handle actions first (no duplicate labels/IDs)
        if write_clicked:
            try:
                with engine.begin() as cx:
                    _write_test_audit(cx)
                st.session_state.audit_last_write_ts = time.time()
                st.success("Wrote test audit event.")
                # bump refresh counter so the button key changes and forces a fresh run
                st.session_state.audit_refresh_counter += 1
                st.rerun()
            except Exception as e:
                st.error(f"Failed to write test audit event: {e}")

        if refresh_clicked:
            st.session_state.audit_refresh_counter += 1
            st.rerun()

        # Now fetch and render once per run
        try:
            with engine.connect() as cx:
                df_audit = _fetch_audit_df(cx)
            if df_audit.empty:
                st.caption("No audit events recorded yet.")
            else:
                st.dataframe(df_audit, use_container_width=True, height=360)
        except Exception as e:
            st.error("Failed to fetch audit events.")
            st.exception(e)