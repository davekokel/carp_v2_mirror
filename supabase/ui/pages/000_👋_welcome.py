from __future__ import annotations

import os, sys
from pathlib import Path
import streamlit as st

# Ensure repo root is importable (cloud + local)
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Env + banner
APP_ENV = os.getenv("APP_ENV", "local").lower()
try:
    from supabase.ui.lib.prod_banner import show_prod_banner
    show_prod_banner()
except Exception:
    pass

st.set_page_config(page_title="CARP — Welcome", page_icon="👋", layout="wide")

st.title("👋 Welcome to CARP")
st.write("Browse live data, upload CSVs, and print labels — no install needed.")

# Quick status
cols = st.columns(3)
with cols[0]:
    st.metric("Environment", APP_ENV.upper())
with cols[1]:
    st.metric("Mode", os.getenv("APP_MODE", "readonly" if os.getenv("PGUSER","").endswith("_ro") else "write"))
with cols[2]:
    st.metric("Database host", os.getenv("PGHOST","").split(".supabase.co")[0] + ".supabase.co" if os.getenv("PGHOST") else "—")

st.divider()

# Quick links (Streamlit 1.38+: st.page_link)
st.subheader("Start here")

gl = st.columns(3)
with gl[0]:
    st.page_link("pages/001_🧪_diagnostics_clean.py", label="Diagnostics", icon="🧪")
with gl[1]:
    st.page_link("pages/020_🔎_overview_fish.py", label="Overview — Fish", icon="🐟")
with gl[2]:
    st.page_link("pages/021_🔎_overview_tanks.py", label="Overview — Tanks", icon="🧱")

gl2 = st.columns(3)
with gl2[0]:
    st.page_link("pages/010_📤_upload_csv_fish.py", label="Upload CSV — Fish", icon="📤")
with gl2[1]:
    st.page_link("pages/011_📤_upload_csv_plasmids.py", label="Upload CSV — Plasmids", icon="🧬")
with gl2[2]:
    st.page_link("pages/03_🏷️_request_tank_labels.py", label="Print Tank Labels", icon="🏷️")

st.divider()

# Friendly guard for read-only deployments
app_mode = os.getenv("APP_MODE", "").lower()
pguser = os.getenv("PGUSER","")
is_readonly = (app_mode != "write") or pguser.endswith("_ro")

if is_readonly:
    st.info("Uploads and edits may be disabled in this deployment. You can still browse data and print labels.")
    with st.expander("Need to upload?"):
        st.write("If you need write access here, ping the admin to enable the write-capable app or grant permission.")
else:
    st.success("This deployment allows uploads and edits.")

st.caption("Tip: Use the left sidebar anytime to jump between pages.")