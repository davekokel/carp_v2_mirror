from __future__ import annotations
# supabase/ui/streamlit_app.py
# supabase/ui/streamlit_app.py
# --- sys.path before local imports ---
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]  # project root (…/carp_v2)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import os
from urllib.parse import urlparse
import streamlit as st
from supabase.ui.lib.app_ctx import set_db_url, get_engine, engine_info
from supabase.ui.lib_shared import db_picker, connection_info
# 🔒 require password on every page
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
PAGE_TITLE = "Cell Observatory — CARP"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🐟", layout="wide")
require_app_unlock()
st.title("🐟 CARP")
st.caption("Centralized Aquatic Resource Pipeline")
# ---------- Central DB picker (authority for the whole app) ----------
eng, DB_URL = db_picker(show_ui=True)  # stores DB_URL in st.session_state
dbg = connection_info(eng)
st.caption(f"DB debug → db={dbg['db']} user={dbg['user']}")
st.markdown(
    """
Welcome! Use the actions below to work with the fish database.  
Start by uploading seedkit CSVs (allele numbers can be assigned automatically).
"""
)
# --- Navigation ---
st.subheader("Go to")
col1, col2 = st.columns([1, 1], gap="large")
with col1:
    st.page_link(
        "pages/01_📤_upload_fish_seedkit.py",
        label="📤 Upload Fish Seedkit",
        help="CSV with DB-aligned headers; `allele_nickname` (e.g., abc-1) is parsed to a number.",
    )
with col2:
    st.link_button(
        "📖 Seedkit Upload Docs",
        url="https://github.com/cell-observatory/carp_v2/blob/main/docs/Upload_Fish_Seedkit.md",
        help="CSV contract, allocator behavior, and verification SQL.",
        width="content",
    )

st.divider()

# --- Status (masked DB info) ---
def _mask_url_password(url: str) -> str:
    try:
        u = urlparse(url or "")
        netloc = u.netloc
        if "@" in netloc:
            creds, host = netloc.split("@", 1)
            user = creds.split(":", 1)[0]
            netloc = f"{user}:***@{host}"
        return u._replace(netloc=netloc).geturl()
    except Exception:
        return "(unavailable)"

with st.expander("Connection/status", expanded=False):
    env = st.secrets.get("APP_ENV", os.getenv("APP_ENV", "prod"))
    st.write(f"**Environment:** `{env}`")
    # Prefer the selected URL (db_picker stored it in session), fall back to secrets/env
    db_url = st.session_state.get("DB_URL") or st.secrets.get("DB_URL") or os.getenv("DATABASE_URL", "")
    if db_url:
        st.write("**DB URL (masked):**")
        st.code(_mask_url_password(db_url))
    else:
        st.warning("No DB URL found. Set `DB_URL` or `DATABASE_URL`, or choose Local via the picker above.")

st.caption("If you need another entry point later (inspection, QC, etc.), we’ll add links here.")

# --- Central DB picker (minimal, idempotent) ---
import os
from urllib.parse import urlparse

def _mask(u: str) -> str:
    try:
        p = urlparse(u or "")
        if "@" in p.netloc:
            user, host = p.netloc.split("@", 1)
            user = user.split(":", 1)[0]
            netloc = f"{user}:***@{host}"
        else:
            netloc = p.netloc
        return p._replace(netloc=netloc).geturl()
    except Exception:
        return u

with st.expander("Connection (centralized)", expanded=False):
    local_default = "postgresql://postgres@localhost:5432/postgres?sslmode=disable"
    env_default = os.getenv("DB_URL") or os.getenv("DATABASE_URL") or local_default

    choice = st.radio("Choose DB target", ["Local", "Env/Default", "Custom"], horizontal=True, key="db_choice_appctx")
    custom = st.text_input(
        "Custom DB URL",
        value=st.session_state.get("DB_URL","") if choice=="Custom" else "",
        placeholder=env_default,
        key="db_custom_appctx"
    )

    selected = local_default if choice=="Local" else (env_default if choice=="Env/Default" else (custom.strip() or env_default))
    colA, colB = st.columns([1,1])
    with colA:
        if st.button("Connect", key="connect_appctx"):
            set_db_url(selected)
            st.success("Reconnected. Engine cache cleared.")
            st.experimental_rerun()
    with colB:
        try:
            dbg = engine_info(get_engine())
            st.caption(f"DB debug → db={dbg['db']} user={dbg['usr']} host={dbg['host']}:{dbg['port']}")
            st.code(_mask(selected), language="text")
        except Exception as e:
            st.error(f"Engine error: {e}")
