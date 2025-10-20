from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.lib.db import get_engine

sb, session, user = require_auth()
require_email_otp()
st.set_page_config(page_title="Manage Tanks for Fish", page_icon="🐟", layout="wide")
st.title("🐟 Manage Tanks for Fish")

eng = get_engine()

@st.cache_data(ttl=5, show_spinner=False)
def load_tanks(fish_code: str) -> pd.DataFrame:
    if not fish_code:
        return pd.DataFrame()
    with eng.begin() as cx:
        df = pd.read_sql(
            text("""
                select fish_code, tank_id, tank_code, status, capacity, tank_created_at, tank_updated_at
                from public.v_tanks_for_fish
                where fish_code = :fc
                order by tank_created_at
            """),
            cx,
            params={"fc": fish_code},
        )
    return df

def add_active_tank(fish_code: str, capacity: int | None):
    with eng.begin() as cx:
        tank_code = cx.execute(
            text("""
                select public.fn_add_active_tank_for_fish(id, :cap)
                from public.fish
                where fish_code = :fc
            """),
            {"fc": fish_code, "cap": capacity},
        ).scalar()
    return tank_code

def set_status(tank_id: str, status: str):
    with eng.begin() as cx:
        cx.execute(text("select public.fn_set_tank_status(:id, :st)"), {"id": tank_id, "st": status})

def set_capacity(tank_id: str, capacity: int | None):
    with eng.begin() as cx:
        cx.execute(text("select public.fn_set_tank_capacity(:id, :cap)"), {"id": tank_id, "cap": capacity})

with st.sidebar:
    fish_code = st.text_input("Fish code", placeholder="FSH-250002").strip().upper()
    cap_new = st.number_input("Capacity for new active tank (optional)", min_value=0, step=1, value=0)
    if st.button("➕ Add active tank", use_container_width=True, disabled=(not fish_code)):
        cap_val = None if cap_new == 0 else int(cap_new)
        try:
            code = add_active_tank(fish_code, cap_val)
            st.success(f"Created {code}")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Add tank failed: {e}")

if not fish_code:
    st.info("Enter a fish code to view/manage tanks.")
    st.stop()

df = load_tanks(fish_code)
if df.empty:
    st.warning("No tanks found yet for this fish.")
else:
    st.subheader(f"Fish {fish_code} — {len(df)} tank(s)")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### Edit tank rows")
    statuses = ["new_tank","active","quarantined","retired","cleaning","broken","decommissioned"]

    for _, row in df.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([2,2,2,2,2])
            c1.markdown(f"**{row.tank_code}**")
            status_sel = c2.selectbox("Status", statuses, index=statuses.index(row.status), key=f"status_{row.tank_id}")
            cap_val = c3.number_input("Capacity", min_value=0, step=1, value=int(row.capacity or 0), key=f"cap_{row.tank_id}")
            do_status = c4.button("Set status", key=f"setst_{row.tank_id}")
            do_cap = c5.button("Set capacity", key=f"setcap_{row.tank_id}")
            if do_status:
                try:
                    set_status(str(row.tank_id), status_sel)
                    st.success(f"Updated status → {status_sel} for {row.tank_code}")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Set status failed: {e}")
            if do_cap:
                try:
                    set_capacity(str(row.tank_id), int(cap_val) if cap_val > 0 else None)
                    st.success(f"Updated capacity → {cap_val} for {row.tank_code}")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Set capacity failed: {e}")