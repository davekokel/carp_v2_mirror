# carp_app/ui/pages/091_🔎_overview_tanks.py
from __future__ import annotations
import sys, pathlib, os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.lib.db import get_engine as _create_engine
from carp_app.lib.time import utc_now

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Overview Tanks", page_icon="🔎", layout="wide")
st.title("🔎 Overview tanks")

@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

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

def _load_tanks_overview(q: Optional[str], status_filter: str, limit: int) -> pd.DataFrame:
    where = ["1=1"]
    params = {"lim": int(limit)}
    if q and q.strip():
        params["ql"] = f"%{q.strip()}%"
        where.append("(COALESCE(tank_code,'') ILIKE :ql OR COALESCE(fish_code,'') ILIKE :ql OR COALESCE(status,'') ILIKE :ql)")
    if status_filter and status_filter != "All":
        params["st"] = status_filter
        where.append("COALESCE(status,'') = :st")
    sql = text(f"""
      SELECT
        tank_uuid::text AS id,
        tank_code,
        fish_code,
        status,
        created_at
      FROM public.v_tanks
      WHERE {' AND '.join(where)}
      ORDER BY created_at DESC NULLS LAST, tank_code
      LIMIT :lim
    """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params=params)

def _render_tanks(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No rows match your filters.")
        return
    out = df.copy()
    out["since_days"] = [ _since_days(ts) for ts in out.get("created_at", []) ]
    out = out.rename(columns={
        "tank_code": "Tank code",
        "fish_code": "fish_code",
        "status": "Status",
        "since_days": "Since (days)",
        "created_at": "Created",
        "id": "ID",
    })
    cols = [c for c in ["Tank code","fish_code","Status","Since (days)","Created","ID"] if c in out.columns]
    st.caption(f"{len(out)} matches")
    st.dataframe(out[cols], use_container_width=True, hide_index=True)

def main():
    with st.form("filters"):
        c1, c2, c3 = st.columns([3,1,1])
        with c1:
            q_raw = st.text_input("Search (tank_code / fish_code / status)", "")
        with c2:
            status = st.selectbox("Status", ["active","to_kill","inactive","All"], index=0)
        with c3:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        st.form_submit_button("Apply")

    q = (q_raw or "").strip()
    try:
        df = _load_tanks_overview(q=q, status_filter=status, limit=limit)
    except Exception as e:
        st.error(f"Query error: {type(e).__name__}: {e}")
        with st.expander("Debug"):
            st.code(str(e))
        return

    _render_tanks(df)

    with st.expander("Debug"):
        st.write({"q_raw": q_raw, "q": q, "limit": limit, "status_filter": status})
        try:
            with _get_engine().connect() as cx:
                cnt = cx.execute(text("select count(*) from public.v_tanks")).scalar()
                sample = pd.read_sql(
                    text("select tank_uuid::text as id, tank_code, fish_code, status, created_at from public.v_tanks order by created_at desc nulls last limit 10"),
                    cx
                )
            st.write({"v_tanks_count": int(cnt)})
            st.dataframe(sample, use_container_width=True, hide_index=True)
        except Exception as e:
            st.write({"v_tanks_error": str(e)})

if __name__ == "__main__":
    main()