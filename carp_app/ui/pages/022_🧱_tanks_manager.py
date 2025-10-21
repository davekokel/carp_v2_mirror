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
STATUSES = ["new_tank","active","quarantined","retired","cleaning","broken","decommissioned"]

@st.cache_data(ttl=60, show_spinner=False)
def load_fish_options(q: str = "", limit: int = 200) -> list[dict]:
    q = (q or "").strip()
    pat = f"%{q.upper()}%" if q else ""
    sql = text("""
      select id, fish_code, coalesce(nickname, name, '') as label
      from public.fish
      where (:q = '' or upper(fish_code) like :pat or upper(coalesce(nickname,'')) like :pat)
      order by fish_code desc
      limit :lim
    """)
    with eng.begin() as cx:
        rows = cx.execute(sql, {"q": q, "pat": pat, "lim": int(limit)}).mappings().all()
    return [{"id": r["id"], "label": f'{r["fish_code"]} — {r["label"]}'.rstrip(" —")} for r in rows]

@st.cache_data(ttl=30, show_spinner=False)
def load_tanks(q: str = "", limit: int = 500) -> pd.DataFrame:
    q = (q or "").strip()
    pat = f"%{q.upper()}%" if q else ""
    sql = text("""
      select
        vt.tank_id::text as tank_id,
        vt.tank_code,
        vt.status::text as status,
        vt.capacity,
        vt.fish_id::text as fish_id,
        f.fish_code,
        vt.tank_created_at as created_at,
        vt.tank_updated_at as updated_at
      from public.v_tanks vt
      join public.fish f on f.id = vt.fish_id
      where (:q = '' or upper(vt.tank_code) like :pat or upper(f.fish_code) like :pat)
      order by vt.tank_created_at desc nulls last
      limit :lim
    """)
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params={"q": q, "pat": pat, "lim": int(limit)})

def add_active_tank_for_fish(fish_id: str, capacity: int | None) -> str:
    sql = text("select public.fn_add_active_tank_for_fish(:fish_id, :capacity)")
    with eng.begin() as cx:
        return cx.execute(sql, {"fish_id": fish_id, "capacity": capacity}).scalar()

def set_status(tank_id: str, status: str) -> None:
    sql = text("select public.fn_set_tank_status(:tank_id, :status::public.tank_status)")
    with eng.begin() as cx:
        cx.execute(sql, {"tank_id": tank_id, "status": status})

def set_capacity(tank_id: str, capacity: int | None) -> None:
    sql = text("select public.fn_set_tank_capacity(:tank_id, :capacity)")
    with eng.begin() as cx:
        cx.execute(sql, {"tank_id": tank_id, "capacity": capacity})

tab1, tab2 = st.tabs(["➕ Add tank for a fish", "🎛️ Manage tank status"])

with tab1:
    st.subheader("Add active tank")
    c1, c2 = st.columns([2, 1])
    with c1:
        q = st.text_input("Search fish", "")
        fish_opts = load_fish_options(q)
        labels = [o["label"] for o in fish_opts] or ["— none —"]
        fish_label = st.selectbox("Fish", labels, index=0)
    with c2:
        cap = st.number_input("Capacity (optional)", min_value=0, step=1, value=0)
    can_add = bool(fish_opts) and fish_label in labels
    if st.button("Create active tank", type="primary", use_container_width=True, disabled=not can_add):
        try:
            fish_id = next(o["id"] for o in fish_opts if o["label"] == fish_label)
            code = add_active_tank_for_fish(fish_id, int(cap) if cap > 0 else None)
            st.success(f"Created {code}")
            st.cache_data.clear()
        except Exception as e:
            st.error(str(e))

with tab2:
    st.subheader("Status & capacity")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        tq = st.text_input("Filter tanks (by tank_code or fish_code)", "")
    with c2:
        limit = st.number_input("Limit", min_value=1, max_value=5000, value=500, step=50)
    with c3:
        st.write("")
        st.write("")
        if st.button("Refresh"):
            st.cache_data.clear()

    df = load_tanks(tq, int(limit))
    if df.empty:
        st.info("No tanks match the filter.")
    else:
        view = df.rename(columns={
            "tank_code": "Tank",
            "status": "Status",
            "capacity": "Capacity",
            "fish_code": "Fish",
            "created_at": "Created",
            "updated_at": "Updated",
        }).copy()
        st.dataframe(view[["Tank","Fish","Status","Capacity","Created","Updated"]], use_container_width=True, hide_index=True)

        st.markdown("### Edit selected tank")
        tank_choices = [f'{r.tank_code} — {r.fish_code} (status={r.status})' for r in df.itertuples(index=False)]
        if not tank_choices:
            st.stop()
        pick = st.selectbox("Tank", tank_choices)
        idx = tank_choices.index(pick)
        row = df.iloc[idx]
        n1, n2, n3 = st.columns([1,1,1])
        with n1:
            new_status = st.selectbox("New status", STATUSES, index=STATUSES.index(row["status"]) if row["status"] in STATUSES else 0)
        with n2:
            new_capacity = st.number_input("Capacity", min_value=0, step=1, value=int(row["capacity"] or 0))
        with n3:
            st.write("")
            if st.button("Apply changes", type="primary", use_container_width=True):
                try:
                    set_status(row["tank_id"], new_status)
                    set_capacity(row["tank_id"], int(new_capacity) if new_capacity > 0 else None)
                    st.success(f"Updated {row['tank_code']}: status→{new_status}, capacity→{new_capacity or 'NULL'}")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(str(e))