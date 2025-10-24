from __future__ import annotations
from carp_app.ui.lib.app_ctx import get_engine as _shared_get_engine  # kept for parity

# --- path shim (preserve original behavior) ---
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- auth / gates (preserve) ---
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# --- std libs / third-party ---
import os
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
import streamlit as st
from sqlalchemy import text

# --- app libs ---
from carp_app.lib.db import get_engine as _create_engine
from carp_app.lib.time import utc_now

# ---------- engine (URL-first, cached) ----------
@st.cache_resource(show_spinner=False)
def _cached_engine():
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine():
    return _cached_engine()

PAGE_TITLE = "CARP — Overview Tanks"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🔎", layout="wide")

# ---------- helpers ----------
def _since_days(ts) -> Optional[float]:
    if not ts:
        return None
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return round((utc_now() - ts).total_seconds() / 86400, 1)

def _load_tanks_overview(q: Optional[str], limit: int) -> pd.DataFrame:
    """
    Minimal, tank-centric overview pulled from public.v_tanks.
    Columns returned:
      id, tank_code, fish_code, status, created_at
    """
    sql = text("""
      select
        v.tank_id::text                       as id,
        v.tank_code::text                     as tank_code,
        coalesce(v.fish_code, '')::text       as fish_code,
        coalesce(v.status::text, '')          as status,
        v.tank_created_at                     as created_at
      from public.v_tanks v
      where (
        :q = '' or
        coalesce(v.tank_code,'')      ilike :ql or
        coalesce(v.fish_code,'')      ilike :ql or
        coalesce(v.status::text,'')   ilike :ql
      )
      order by v.tank_created_at desc nulls last, v.tank_code
      limit :lim
    """)
    params = {
        "q": (q or ""),
        "ql": f"%{q or ''}%",
        "lim": int(limit),
    }
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params=params)

def _render_tanks(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No rows match your filters.")
        return

    # derive a “since (days)” column from created_at
    df = df.copy()
    df["since_days"] = [ _since_days(ts) for ts in df.get("created_at", []) ]

    # order + relabel
    order = [c for c in [
        "tank_code", "fish_code", "status",
        "since_days", "created_at", "id"
    ] if c in df.columns]
    df = df[order].rename(columns={
        "tank_code": "Tank code",
        "fish_code": "Fish code",
        "status": "Status",
        "since_days": "Since (days)",
        "created_at": "Created",
        "id": "ID",
    })

    st.caption(f"{len(df)} matches")
    st.dataframe(df, width="stretch", hide_index=True)

# ---------- page ----------
def main():
    st.title("🔎 Overview tanks")

    # Filters
    with st.form("filters"):
        c1, c2 = st.columns([3,1])
        with c1:
            q_raw = st.text_input("Search (tank_code / fish_code / status)", "")
        with c2:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        submitted = st.form_submit_button("Apply")

    q = (q_raw.strip() or None)

    # Query + Render
    try:
        df = _load_tanks_overview(q=q, limit=limit)
    except Exception as e:
        st.error(f"Query error: {type(e).__name__}: {e}")
        with st.expander("Debug"):
            st.code(str(e))
        return

    _render_tanks(df)

    # Debug panel
    with st.expander("Debug"):
        st.write({"q_raw": q_raw, "q": q, "limit": limit})
        try:
            with _get_engine().connect() as cx:
                cnt = cx.execute(text("select count(*) from public.v_tanks")).scalar()
            st.write({"v_tanks_count": int(cnt)})
        except Exception as e:
            st.write({"v_tanks_error": str(e)})

if __name__ == "__main__":
    main()