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

st.subheader("Start here")

from glob import glob

PAGES_DIR = Path(__file__).resolve().parents[0] / "pages"

def find_page(*needles: str) -> str | None:
    if not PAGES_DIR.exists():
        return None
    files = [Path(p).name for p in glob(str(PAGES_DIR / "*.py"))]
    # prefer exact startswith, then substring match
    for n in needles:
        for f in files:
            if f.startswith(n):
                return f
    for n in needles:
        for f in files:
            if n in f:
                return f
    return None

def link_if(found: str | None, label: str, icon: str = ""):
    if found:
        st.page_link(f"pages/{found}", label=label, icon=icon)
    else:
        st.write(f"· {label} (coming soon)")

c1, c2, c3 = st.columns(3)

with c1:
    # Diagnostics
    diag = find_page("001_🧪_diagnostics_clean", "diagnostics_clean", "diagnostics")
    link_if(diag, "Diagnostics", "🧪")

with c2:
    # Overview — Fish (fall back to any 'overview' page)
    ov_fish = find_page("020_🔎_overview_fish", "overview_fish", "overview")
    link_if(ov_fish, "Overview — Fish", "🐟")

with c3:
    # Overview — Tanks
    ov_tanks = find_page("021_🔎_overview_tanks", "overview_tanks", "tanks")
    link_if(ov_tanks, "Overview — Tanks", "🧱")

c4, c5, c6 = st.columns(3)

with c4:
    # Upload CSV — Fish
    up_fish = find_page("010_📤_upload_csv_fish", "upload_csv_fish", "upload_csv")
    link_if(up_fish, "Upload CSV — Fish", "📤")

with c5:
    # Upload CSV — Plasmids
    up_plasmids = find_page("011_📤_upload_csv_plasmids", "upload_csv_plasmids", "plasmids")
    link_if(up_plasmids, "Upload CSV — Plasmids", "🧬")

with c6:
    # Print Tank Labels
    labels = find_page("03_🏷️_request_tank_labels", "request_tank_labels", "labels")
    link_if(labels, "Print Tank Labels", "🏷️")

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