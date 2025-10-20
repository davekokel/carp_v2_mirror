from __future__ import annotations
import sys, pathlib
import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.lib.db import get_engine

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="Overview — Tanks", page_icon="🧪", layout="wide")
st.title("🔎 Overview — Tanks")
_qp = st.query_params
_q_default = (_qp.get("fish", [None])[0] or "").strip().upper()


eng = get_engine()

# --- DB diagnostics + ensure view exists ---
with eng.begin() as cx:
    db_row = cx.execute(text("select current_database() db, inet_server_addr()::text host, current_user usr")).fetchone()
    tz = cx.execute(text("select current_setting('TimeZone')")).scalar()
    try:
        url = getattr(eng, "url", None)
        url_str = str(url) if url else "(no url)"
    except Exception:
        url_str = "(no url)"

with st.expander("DB diagnostics", expanded=False):
    st.code(f"DB_URL (engine): {url_str}\nDB: {db_row.db}  host: {db_row.host}  user: {db_row.usr}  tz: {tz}")

def _view_exists() -> bool:
    with eng.begin() as cx:
        return bool(cx.execute(text("""
            select 1
            from information_schema.views
            where table_schema='public' and table_name='v_tanks_for_fish'
            limit 1
        """)).fetchone())

def _create_view_now():
    sql = """
    create or replace view public.v_tanks_for_fish as
    select
      t.id as tank_id,
      t.tank_code,
      t.status,
      t.capacity,
      t.created_at as tank_created_at,
      t.updated_at as tank_updated_at,
      f.id as fish_id,
      f.fish_code
    from public.tanks t
    join public.fish f on f.id = t.fish_id;
    """
    with eng.begin() as cx:
        cx.execute(text(sql))

cols = st.columns([1,1,6])
with cols[0]:
    if st.button("Check view"):
        st.info("v_tanks_for_fish exists ✅" if _view_exists() else "v_tanks_for_fish is missing ❌")
with cols[1]:
    if st.button("Create view now"):
        try:
            _create_view_now()
            st.success("Created public.v_tanks_for_fish ✅")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Create view failed: {e}")
# --- end diagnostics ---

STATUSES = ["new_tank","active","quarantined","retired","cleaning","broken","decommissioned"]

def _assert_view_exists():
    with eng.begin() as cx:
        row = cx.execute(text("""
            select 1
            from information_schema.views
            where table_schema='public' and table_name='v_tanks_for_fish'
            limit 1
        """)).fetchone()
    if not row:
        st.error("Required view public.v_tanks_for_fish is missing. Run the migration supabase/migrations/20251020_v_tanks_for_fish.sql.")
        st.stop()

@st.cache_data(ttl=5, show_spinner=False)
def load_tanks(q: str | None, statuses: list[str], limit: int) -> pd.DataFrame:
    _assert_view_exists()
    where = []
    params: dict[str, object] = {"limit": int(limit)}
    if q:
        params["q"] = f"%{q.upper()}%"
        where.append("(upper(fish_code) like :q or upper(tank_code) like :q)")
    if statuses:
        where.append("status::text = any(:statuses)")
        params["statuses"] = statuses

    sql = """
    select fish_code, tank_id, tank_code, status, capacity, tank_created_at, tank_updated_at
    from public.v_tanks_for_fish
    """ + (" where " + " and ".join(where) if where else "") + " order by tank_created_at desc nulls last limit :limit"

    with eng.begin() as cx:
        return pd.read_sql(text(sql), cx, params=params)

def set_status(tank_id: str, status: str):
    with eng.begin() as cx:
        cx.execute(text("select public.fn_set_tank_status(:id,:st)"), {"id": tank_id, "st": status})

def set_capacity(tank_id: str, capacity: int | None):
    with eng.begin() as cx:
        cx.execute(text("select public.fn_set_tank_capacity(:id,:cap)"), {"id": tank_id, "cap": capacity})

def add_active_tank_for_fish(fish_code: str, capacity: int | None):
    with eng.begin() as cx:
        return cx.execute(
            text("""
                select public.fn_add_active_tank_for_fish(id, :cap)
                from public.fish
                where fish_code = :fc
            """),
            {"fc": fish_code, "cap": capacity},
        ).scalar()

with st.sidebar:
    q = st.text_input("Search (fish_code or tank_code)", value=_q_default).strip()
    statuses = st.multiselect("Statuses", STATUSES, default=["active","new_tank"])
    limit = st.number_input("Limit", min_value=1, max_value=5000, value=200, step=50)
    fish_for_new = st.text_input("Add active tank for fish_code").strip().upper()
    cap_new = st.number_input("Capacity (optional)", min_value=0, step=1, value=0)
    if st.button("➕ Add active tank", use_container_width=True, disabled=(not fish_for_new)):
        try:
            cap_val = None if cap_new == 0 else int(cap_new)
            code = add_active_tank_for_fish(fish_for_new, cap_val)
            st.success(f"Created {code}")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Add tank failed: {e}")

df = load_tanks(q or None, statuses, int(limit))
if df.empty:
    st.info("No tanks match your filters.")
    st.stop()

st.caption(f"{len(df)} tank(s) shown")
st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("### Edit tanks")
for _, row in df.iterrows():
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([2,2,2,2,2])
        c1.markdown(f"**{row.tank_code}**  \n{row.fish_code}")
        st_new = c2.selectbox("Status", STATUSES, index=STATUSES.index(row.status), key=f"st_{row.tank_id}")
        cap_val = int(row.capacity) if pd.notnull(row.capacity) else 0
        cap_new = c3.number_input("Capacity", min_value=0, step=1, value=cap_val, key=f"cap_{row.tank_id}")
        if c4.button("Set status", key=f"setst_{row.tank_id}"):
            try:
                set_status(str(row.tank_id), st_new)
                st.success(f"Status → {st_new} for {row.tank_code}")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Set status failed: {e}")
        if c5.button("Set capacity", key=f"setcap_{row.tank_id}"):
            try:
                set_capacity(str(row.tank_id), int(cap_new) if cap_new > 0 else None)
                st.success(f"Capacity → {cap_new} for {row.tank_code}")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Set capacity failed: {e}")
