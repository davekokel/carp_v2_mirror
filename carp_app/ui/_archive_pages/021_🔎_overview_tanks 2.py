from __future__ import annotations

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
from typing import List, Mapping, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

# --- engine (URL-first, cached) ---
from carp_app.lib.db import get_engine as _create_engine

@st.cache_resource(show_spinner=False)
def _cached_engine():
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine():
    return _cached_engine()

# --- queries ---
from carp_app.lib.queries import load_containers_overview

PAGE_TITLE = "CARP — Overview Search (Tanks)"
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
    return round((datetime.now(timezone.utc) - ts).total_seconds() / 86400, 1)

def _render_containers(rows: list[Mapping]) -> None:
    if not rows:
        st.info("No rows match your filters.")
        return
    df = pd.DataFrame(rows)

    # derive a “since (days)” column from status_changed_at or created_at
    since = []
    for _, r in df.iterrows():
        ts = r.get("status_changed_at") or r.get("created_at")
        since.append(_since_days(ts))
    df["since_days"] = since

    # order + relabel for humans
    order = [c for c in [
        "tank_code", "label", "container_type", "status",
        "since_days", "status_changed_at", "created_at", "id"
    ] if c in df.columns]
    df = df[order].rename(columns={
        "tank_code": "Tank code",
        "label": "Label",
        "container_type": "Type",
        "status": "Status",
        "since_days": "Since (days)",
        "status_changed_at": "Status changed",
        "created_at": "Created",
        "id": "ID",
    })

    st.caption(f"{len(df)} matches")
    st.dataframe(df, use_container_width=True, hide_index=True)

# ---------- page ----------
def main():
    st.title("🔎 Overview Tanks")

    # Filters form (keep layout; stage kept as a visual no-op for now)
    with st.form("filters"):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            q_raw = st.text_input("Search (multi-term; quotes & -negation supported)", "")
        with c2:
            st.selectbox("Stage", options=["(not used for tanks)"], index=0, disabled=True)
        with c3:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        submitted = st.form_submit_button("Apply")

    # Normalize empty input → None so empty search returns all rows
    q = (q_raw.strip() or None)

    # Query
    try:
        rows = load_containers_overview(_get_engine(), q=q, limit=limit)
    except Exception as e:
        st.error(f"Query error: {type(e).__name__}: {e}")
        with st.expander("Debug"):
            st.code(str(e))
        return

    # Render
    _render_containers(rows)

    # Debug panel (kept from original page style)
    with st.expander("Debug"):
        st.write({"q_raw": q_raw, "q": q, "limit": limit})
        try:
            with _get_engine().connect() as cx:
                cnt = cx.execute(text("select count(*) from public.v_containers_overview")).scalar()
            st.write({"v_containers_overview": int(cnt)})
        except Exception as e:
            st.write({"view_count_error": str(e)})

if __name__ == "__main__":
    main()