# carp_app/ui/pages/091_🔎_overview_tanks.py
from __future__ import annotations
import os, sys, pathlib
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine as _create_engine
from carp_app.lib.time import utc_now

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Overview Tanks", page_icon="🔎", layout="wide")
st.title("🔎 Overview tanks")

# ───────── engine ─────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

# ───────── helpers ─────────
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

def _load_statuses() -> list[str]:
    sql = text("SELECT DISTINCT COALESCE(status,'') AS s FROM public.v_tanks_overview ORDER BY 1")
    with _get_engine().begin() as cx:
        vals = [r["s"] for r in cx.execute(sql).mappings().all()]
    preferred = ["active","to_kill","inactive"]
    return [s for s in preferred if s in vals] + [s for s in vals if s not in preferred]

# ───────── data loader ─────────
def _load_tanks_overview(q: Optional[str], status_filter: str, limit: int) -> pd.DataFrame:
    where = ["1=1"]
    params = {"lim": int(limit)}

    if q and q.strip():
        params["ql"] = f"%{q.strip()}%"
        where.append("("
                     "COALESCE(tank_code,'') ILIKE :ql OR "
                     "COALESCE(fish_code,'') ILIKE :ql OR "
                     "COALESCE(status,'') ILIKE :ql"
                     ")")
    if status_filter and status_filter != "All":
        params["st"] = status_filter
        where.append("COALESCE(status,'') = :st")

    sql = text(f"""
      SELECT id, tank_code, fish_code, status, created_at
      FROM public.v_tanks_overview
      WHERE {' AND '.join(where)}
      ORDER BY created_at DESC NULLS LAST, tank_code
      LIMIT :lim
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include=["object","string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

# ───────── renderer ─────────
def _render_tanks(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No rows match your filters.")
        return
    out = df.copy()
    out["Since (days)"] = [_since_days(ts) for ts in out.get("created_at", [])]
    out = out.rename(columns={
        "tank_code": "Tank code",
        "fish_code": "Fish code",
        "status":    "Status",
        "created_at":"Created",
        "id":        "ID",
    })
    cols = [c for c in ["Tank code","Fish code","Status","Since (days)","Created","ID"] if c in out.columns]
    st.caption(f"{len(out)} matches")
    st.dataframe(out[cols], width="stretch", hide_index=True)

# ───────── page ─────────
def main():
    statuses = _load_statuses() or ["active","to_kill","inactive"]

    with st.form("filters", clear_on_submit=False):
        c1, c2, c3 = st.columns([3,1,1])
        with c1:
            q_raw = st.text_input("Search (tank_code / fish_code / status)", "")
        with c2:
            status = st.selectbox("Status", statuses + ["All"], index=0)
        with c3:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        _ = st.form_submit_button("Apply")

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
        try:
            with _get_engine().connect() as cx:
                cnt = cx.execute(text("SELECT count(*) FROM public.v_tanks_overview")).scalar()
                sample = pd.read_sql(
                    text("""
                      SELECT id, tank_code, fish_code, status, created_at
                      FROM public.v_tanks_overview
                      ORDER BY created_at DESC NULLS LAST
                      LIMIT 10
                    """),
                    cx
                )
            st.write({"view": "public.v_tanks_overview", "rows_in_view": int(cnt)})
            st.dataframe(sample, width="stretch", hide_index=True)
        except Exception as e:
            st.write({"view_check_error": str(e)})

if __name__ == "__main__":
    main()