# pages/00_Health.py

import os
import streamlit as st

from lib.authz import require_app_access, read_only_banner, logout_button
from lib.db import get_engine, fetch_df, exec_sql
from lib.audit import log_event  # used for the test write

st.set_page_config(page_title="CARP — Health", layout="wide")

# ── Gate + banner + logout ─────────────────────────────────────────────────────
require_app_access("🔐 CARP — Private")
read_only_banner()
logout_button("sidebar")

st.title("Health")

# ── Environment info (no DB access here) ───────────────────────────────────────
env_name = st.secrets.get("ENV_NAME", "(unset)")
read_only = st.secrets.get("READ_ONLY", False)
timeout = st.secrets.get("TIMEOUT_MINUTES", 0)
audit    = st.secrets.get("AUDIT_ENABLED", False)

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
    if st.button("Test POOL connection", key="btn_test_pool"):
        _test_dsn("CONN_POOL", st.secrets.get("CONN_POOL"))

with right:
    if st.button("Test DIRECT connection", key="btn_test_direct"):
        _test_dsn("CONN_DIRECT", st.secrets.get("CONN_DIRECT"))

st.caption("These tests only run when you press the button, so the page won’t crash if the DB is unreachable.")

# ── Audit viewer (uses pool DSN) ───────────────────────────────────────────────
st.divider()
st.subheader("Audit log")

POOL_DSN = st.secrets.get("CONN_POOL")

audit_box = st.container()  # placeholder to render/refresh audit list

def render_audit():
    if not POOL_DSN:
        with audit_box:
            st.warning("CONN_POOL is not set; cannot read audit events.")
        return

    try:
        engine = get_engine(POOL_DSN)
        with engine.connect() as cx:
            df = fetch_df(
                cx,
                """
                select happened_at, actor, action, details
                from public.audit_events
                order by happened_at desc
                limit 50
                """
            )
        with audit_box:
            if df.empty:
                st.caption("No audit events recorded yet.")
            else:
                st.dataframe(df, use_container_width=True)
    except Exception as e:
        with audit_box:
            st.error("Failed to load audit events.")
            st.exception(e)

# Top row of audit actions (unique keys avoid duplicate element IDs)
col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Refresh audit list", key="btn_audit_refresh"):
        render_audit()
with col2:
    if st.button("Write test audit row", key="btn_audit_write"):
        # Try to write through log_event(); fall back to raw SQL if needed.
        if not POOL_DSN:
            st.error("CONN_POOL is not set; cannot write test event.")
        else:
            try:
                engine = get_engine(POOL_DSN)
                with engine.begin() as cx:
                    # Prefer the helper if AUDIT_ENABLED and table exists
                    try:
                        log_event(cx, "health_test", {"note": "manual test from Health page"})
                    except Exception:
                        # Fallback raw insert (actor is the shared app user)
                        exec_sql(
                            cx,
                            """
                            insert into public.audit_events (happened_at, actor, action, details)
                            values (now(), current_user, 'health_test', '{"note":"manual test"}'::jsonb)
                            """,
                        )
                st.success("Wrote test audit event.")
            except Exception as e:
                st.error("Failed to write test audit event.")
                st.exception(e)
        # Immediately refresh the list in-place
        render_audit()

# Initial render on first load
render_audit()