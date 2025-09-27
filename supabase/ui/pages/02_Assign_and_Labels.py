import streamlit as st
from lib.db import fetch_df, exec_sql
import pandas as pd
from lib_shared import pick_environment
# pages/*.py
from lib.db import get_engine
engine = get_engine()
from lib.schema import ensure_tank_schema
from lib.queries import sql_batches, detect_tank_select_join, sql_overview, sql_auto_assign
from components.fish_table import render_select_table
from components.labels import generate_labels
from lib.authz import require_app_access
require_app_access("🔐 CARP — Private")

st.set_page_config(page_title="Assign & Labels", layout="wide")
st.title("Assign Tanks & Print Labels")

env, conn = pick_environment()
engine = get_engine(conn)

# Ensure schema
with engine.begin() as cx:
    ensure_tank_schema(cx)

# Pick batch
with engine.connect() as cx:
    batches = fetch_df(cx, sql_batches())["batch"].tolist()
batch_choice = st.selectbox("Filter by batch", batches, index=0)

# Load data for batch
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

col1, col2 = st.columns([1,1], gap="large")

with col1:
    if st.button("Auto-assign tanks (inactive) for this batch"):
        try:
            with engine.begin() as cx:
                exec_sql(cx, sql_auto_assign(), {"batch": batch_choice})
            st.success(f"Auto-assigned tanks for batch: {batch_choice}")
            st.rerun()
        except Exception as e:
            st.error(f"Auto-assign failed: {e}")

with col2:
    def set_status(new_status: str):
        if not selected_ids:
            st.warning("Select at least one fish first.")
            return
        try:
            with engine.begin() as cx:
                # ensure a row exists for each selected fish
                exec_sql(cx, """
                    INSERT INTO public.tank_assignments(fish_id, tank_label, status)
                    SELECT UNNEST(:ids)::uuid, public.next_tank_code('TANK-'), 'inactive'
                    ON CONFLICT (fish_id) DO NOTHING;
                """, {"ids": selected_ids})
                exec_sql(cx, """
                    UPDATE public.tank_assignments
                    SET status = :st::tank_status
                    WHERE fish_id = ANY(:ids);
                """, {"st": new_status, "ids": selected_ids})
            st.success(f"Updated status → {new_status} for {len(selected_ids)} fish")
            st.rerun()
        except Exception as e:
            st.error(f"Status update failed: {e}")

    c1, c2, c3 = st.columns(3)
    with c1: st.button("Activate (alive)", on_click=lambda: set_status("alive"))
    with c2: st.button("Mark to_kill", on_click=lambda: set_status("to_kill"))
    with c3: st.button("Mark dead", on_click=lambda: set_status("dead"))

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
                st.download_button("Download labels.pdf", data=pdf_bytes,
                                   file_name="labels.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"Label generation failed: {e}")
