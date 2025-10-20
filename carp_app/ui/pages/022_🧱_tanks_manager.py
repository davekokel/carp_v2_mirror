from __future__ import annotations
import os
import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.lib.db import get_engine

sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="Tanks Manager", page_icon="🧱", layout="wide")
st.title("🧱 Manage Tank Status & Add Tanks for Fish")

eng = get_engine()

@st.cache_data(ttl=60)
def load_fish_options(q: str = "", limit: int = 200):
    sql = text("""
      select id, fish_code, coalesce(nickname, name, '') as label
      from public.fish
      where ($1 = '' or fish_code ilike '%'||$1||'%' or coalesce(nickname,'') ilike '%'||$1||'%')
      order by fish_code desc
      limit $2
    """)
    with eng.begin() as cx:
        rows = cx.execute(sql, (q, limit)).mappings().all()
    return [{"id": r["id"], "label": f'{r["fish_code"]} — {r["label"]}'.strip(" —")} for r in rows]

@st.cache_data(ttl=30)
def load_tanks():
    sql = text("""
      select t.tank_id, t.tank_code, t.rack, t.position,
             v.status, v.reason, v.changed_at,
             o.n_fish_open
      from public.tanks t
      left join public.v_tanks_current_status v using (tank_id)
      left join public.v_tank_occupancy o using (tank_id)
      order by t.tank_code asc
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx.connection)
    return df

def set_status(tank_id: int, status: str, reason: str):
    sql = text("select public._tank_set_status(:tank_id, :status::public.tank_status, :reason)")
    with eng.begin() as cx:
        cx.execute(sql, {"tank_id": tank_id, "status": status, "reason": reason})

def move_fish(fish_id: int, tank_code: str, rack: str | None, position: str | None, note: str | None):
    sql = text("select public.move_fish_to_tank(:fish_id, :tank_code, :rack, :position, :note)")
    with eng.begin() as cx:
        cx.execute(sql, {"fish_id": fish_id, "tank_code": tank_code, "rack": rack, "position": position, "note": note})

tab1, tab2 = st.tabs(["➕ Add tank for a fish", "🎛️ Manage tank status"])

with tab1:
    st.subheader("Add / Move")
    q = st.text_input("Search fish", "")
    fish_opts = load_fish_options(q)
    fish_map = {o["label"]: o["id"] for o in fish_opts}
    fish_label = st.selectbox("Fish", list(fish_map.keys()) if fish_map else ["— none —"])
    colA, colB, colC = st.columns([2,1,1])
    with colA:
        new_tank_code = st.text_input("Tank code (e.g., TANK-251234)")
    with colB:
        rack = st.text_input("Rack (optional)")
    with colC:
        position = st.text_input("Position (optional)")
    note = st.text_input("Move note (optional)")

    if st.button("Move fish to tank / Create if needed", use_container_width=True, type="primary", disabled=not fish_map or not new_tank_code.strip()):
        try:
            move_fish(fish_map[fish_label], new_tank_code.strip(), rack or None, position or None, note or None)
            st.success(f"Moved {fish_label} to {new_tank_code.strip()}")
            st.cache_data.clear()
        except Exception as e:
            st.error(str(e))

with tab2:
    st.subheader("Set status")
    df = load_tanks()
    st.dataframe(df, use_container_width=True, hide_index=True)
    if len(df):
        pick = st.selectbox("Select tank", [f'{r.tank_code} (status={r.status or "—"}, fish={r.n_fish_open or 0})' for r in df.itertuples()])
        row = df.iloc[[i for i, s in enumerate([f'{r.tank_code} (status={r.status or "—"}, fish={r.n_fish_open or 0})' for r in df.itertuples()]) if s == pick][0]]
        status = st.selectbox("New status", ["vacant","occupied","quarantine","maintenance","retired","decommissioned"], index=["vacant","occupied","quarantine","maintenance","retired","decommissioned"].index(row["status"]) if row["status"] in ["vacant","occupied","quarantine","maintenance","retired","decommissioned"] else 0)
        reason = st.text_input("Reason", "manual change")
        if st.button("Apply status", use_container_width=True):
            try:
                set_status(int(row["tank_id"]), status, reason)
                st.success(f"Set {row['tank_code']} → {status}")
                st.cache_data.clear()
            except Exception as e:
                st.error(str(e))