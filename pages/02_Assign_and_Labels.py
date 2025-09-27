# pages/02_Assign_and_Labels.py

import streamlit as st
st.set_page_config(page_title="Assign & Labels", layout="wide")

from lib_shared import pick_environment
from lib.db import get_engine, fetch_df, exec_sql
from lib.schema import ensure_tank_schema
from lib.queries import (
    sql_batches,
    detect_tank_select_join,
    sql_overview,
    sql_auto_assign,
)
from components.fish_table import render_select_table
from components.labels import generate_labels
import lib.authz as authz           # import module to avoid name shadowing
from lib.audit import log_event

# --- Auth / banners / logout ---
authz.require_app_access("🔐 CARP — Private")
authz.read_only_banner()
authz.logout_button("sidebar")  # global logout in sidebar

st.title("Assign Tanks & Print Labels")

# --- DB engine (env-aware) ---
env, conn = pick_environment()
engine = get_engine(conn)

# --- Ensure schema (safe / idempotent) ---
with engine.begin() as cx:
    ensure_tank_schema(cx)

# --- Pick batch ---
with engine.connect() as cx:
    batches = fetch_df(cx, sql_batches())["batch"].tolist()

if not batches:
    st.info("No batches found yet.")
    st.stop()

batch_choice = st.selectbox("Filter by batch", batches, index=0)

# --- Load data for chosen batch ---
with engine.connect() as cx:
    sel, join = detect_tank_select_join(cx)
    where_sql = "WHERE COALESCE(NULLIF(f.batch_label,''),'(none)') = :batch"
    sql = sql_overview(sel, join, where_sql)
    df = fetch_df(cx, sql, {"batch": batch_choice, "lim": 5000})

selected_ids: list[str] = []
if df.empty:
    st.info("No fish in this batch.")
else:
    selected_ids, edited = render_select_table(df, key="assign_labels_table")
    st.caption(f"Selected: {len(selected_ids)} fish")

col1, col2 = st.columns([1, 1], gap="large")

# --- Auto-assign tanks (inactive) ---
with col1:
    if st.button("Auto-assign tanks (inactive) for this batch", disabled=authz.is_read_only()):
        if authz.is_read_only():
            st.warning("Read-only mode is ON; write actions are disabled.")
            st.stop()
        try:
            with engine.begin() as cx:
                exec_sql(cx, sql_auto_assign(), {"batch": batch_choice})
                log_event(cx, "auto_assign", {"batch": batch_choice})
            st.success(f"Auto-assigned tanks for batch: {batch_choice}")
            st.rerun()
        except Exception as e:
            st.error(f"Auto-assign failed: {e}")

# --- Status updates ---
with col2:

    def set_status(new_status: str) -> bool:
        """Update status for selected fish. Returns True on success."""
        if not selected_ids:
            st.warning("Select at least one fish first.")
            return False
        if authz.is_read_only():
            st.warning("Read-only mode is ON; write actions are disabled.")
            st.stop()

        try:
            # Simple & reliable: only UPDATE. If no rows updated, ask user to auto-assign first.
            with engine.begin() as cx:
                res = exec_sql(
                    cx,
                    """
                    UPDATE public.tank_assignments
                    SET status = CAST(:st AS tank_status)
                    WHERE fish_id = ANY(CAST(:ids AS uuid[]));
                    """,
                    {"st": new_status, "ids": selected_ids},
                )
                # If your exec_sql returns a SQLAlchemy Result, try to get rowcount:
                updated = getattr(res, "rowcount", None)
                if updated == 0:
                    st.warning("No rows updated. Try 'Auto-assign tanks' first for these fish.")
                    return False
                log_event(cx, "status_update", {"status": new_status, "count": updated or len(selected_ids)})

            st.success(f"Updated status → {new_status}")
            return True
        except Exception as e:
            st.error(f"Status update failed: {e}")
            return False

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Activate (alive)", disabled=authz.is_read_only()):
            if set_status("alive"):
                st.rerun()

    with c2:
        if st.button("Mark to_kill", disabled=authz.is_read_only()):
            if set_status("to_kill"):
                st.rerun()

    with c3:
        if st.button("Mark dead", disabled=authz.is_read_only()):
            if set_status("dead"):
                st.rerun()

st.divider()
st.subheader("Labels")

if df.empty:
    st.caption("No data to print.")
else:
    # Only print labels for rows that actually have a tank assigned
    printable = df.loc[df["tank"].fillna("").str.strip() != ""].copy()
    if printable.empty:
        st.warning("No fish with tank codes yet. Auto-assign tanks first.")
    else:
        if st.button("Generate labels PDF (DK-2212)"):
            try:
                pdf_bytes = generate_labels(printable)
                st.download_button(
                    "Download labels.pdf",
                    data=pdf_bytes,
                    file_name="labels.pdf",
                    mime="application/pdf",
                )
            except Exception as e:
                st.error(f"Label generation failed: {e}")