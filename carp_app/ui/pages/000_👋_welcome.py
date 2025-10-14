from __future__ import annotations
from supabase.ui.auth_gate import require_auth
sb, session, user = require_auth()


import os, sys
from pathlib import Path
import streamlit as st

# Ensure repo root is importable (cloud + local)
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Prod/staging banner (if available)
try:
    from supabase.ui.lib.prod_banner import show_prod_banner
    show_prod_banner()
except Exception:
    pass

st.set_page_config(page_title="CARP — Welcome", page_icon="👋", layout="wide")

st.title("👋 Welcome to CARP")
st.write("Browse live data, upload CSVs, and print labels — no install needed. Use the **left sidebar** to navigate.")

# Compact status
APP_ENV = os.getenv("APP_ENV", "local").lower()
pguser  = os.getenv("PGUSER", "")
pghost  = os.getenv("PGHOST", "")
mode    = os.getenv("APP_MODE", "readonly" if pguser.endswith("_ro") else "write")

c1, c2, c3 = st.columns(3)
with c1: st.metric("Environment", APP_ENV.upper())
with c2: st.metric("Mode", mode)
with c3: st.metric("Database host", (pghost.split(".supabase.co")[0] + ".supabase.co") if pghost else "—")

st.divider()

# Friendly guard for read-only deployments
is_readonly = (mode != "write") or pguser.endswith("_ro")
if is_readonly:
    st.info("This deployment is read-only. You can explore data and print labels.")
else:
    st.success("Uploads and edits are enabled in this deployment.")
