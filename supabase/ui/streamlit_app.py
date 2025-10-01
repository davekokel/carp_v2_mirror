# supabase/ui/streamlit_app.py
from __future__ import annotations

import os
from urllib.parse import urlparse
import streamlit as st

# 🔒 require password on every page
try:
    from supabase.ui.auth_gate import require_app_unlock  # deployed/mirror path
except Exception:
    from auth_gate import require_app_unlock  # local path fallback

PAGE_TITLE = "Cell Observatory — CARP"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🐟", layout="wide")

# Run the auth gate after Streamlit is initialized
require_app_unlock()

st.title("🐟 CARP")
st.caption("Centralized Aquatic Resource Pipeline")

st.markdown(
    """
Welcome! Use the actions below to work with the fish database.  
For now, start by uploading seedkit CSVs (DB assigns allele numbers automatically).
"""
)

# --- Navigation ---
st.subheader("Go to")
col1, col2 = st.columns([1, 1], gap="large")
with col1:
    st.page_link(
        "pages/01_📤_upload_fish_seedkit.py",
        label="📤 Upload Fish Seedkit",
        help="CSV with DB-aligned headers; allele_number is assigned by the DB.",
    )
with col2:
    st.link_button(
        "📖 Seedkit Upload Docs",
        url="https://github.com/cell-observatory/carp_v2/blob/main/docs/Upload_Fish_Seedkit.md",
        help="CSV contract, allocator behavior, and verification SQL.",
        use_container_width=False,
    )

st.divider()

# --- Status (masked DB info) ---
def _mask_url_password(url: str) -> str:
    try:
        u = urlparse(url)
        netloc = u.netloc
        if "@" in netloc:
            creds, host = netloc.split("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                netloc = f"{user}:***@{host}"
        return u._replace(netloc=netloc).geturl()
    except Exception:
        return "(unavailable)"

with st.expander("Connection/status", expanded=False):
    env = st.secrets.get("APP_ENV", os.getenv("APP_ENV", "prod"))
    db_url = st.secrets.get("DB_URL", os.getenv("DATABASE_URL", ""))
    st.write(f"**Environment:** `{env}`")
    if db_url:
        st.write("**DB URL (masked):**")
        st.code(_mask_url_password(db_url))
    else:
        st.warning("No DB URL found. Set `DB_URL` in Streamlit secrets (or `DATABASE_URL` env).")

st.caption("If you need another entry point later (inspection, QC, etc.), we’ll add links here.")