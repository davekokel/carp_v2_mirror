from __future__ import annotations
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

import os, sys
from pathlib import Path
import streamlit as st

# Ensure repo root is importable (cloud + local)
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Prod/staging banner (if available)
try:
    from carp_app.ui.lib.prod_banner import show_prod_banner
    show_prod_banner()
except Exception:
    pass

st.set_page_config(page_title="CARP — Welcome", page_icon="👋", layout="wide")

from carp_app.ui.lib.env_badge import show_env_badge
from carp_app.lib.config import DB_URL, AUTH_MODE, env_name

st.title("👋 Welcome to CARP")
show_env_badge()
import os, streamlit as st
from carp_app.lib import secret
# st.caption('RAW_DB_URL: ' + os.getenv('DB_URL','(missing)'))
st.write("Browse live data, upload CSVs, and print labels — no install needed. Use the **left sidebar** to navigate.")


# Compact status (derived from DB_URL)
import re
DB_URL = secret.get("DB_URL","")
m = re.match(r".*://([^:@]+)@([^/?]+)", DB_URL)
_pguser = m.group(1) if m else os.getenv("PGUSER","")
_pghost = m.group(2) if m else os.getenv("PGHOST","")
_proj   = _pguser.split(".",1)[1] if "." in _pguser else "?"

env_name = (
    "PROD"    if (_proj == os.getenv("PROD_PROJECT_ID","") or "prod" in (_pghost or "")) else
    "STAGING" if (_proj == os.getenv("STAGING_PROJECT_ID","") or "staging" in (_pghost or "")) else
    "LOCAL"
)
mode = os.getenv("APP_MODE") or ("readonly" if _pguser.endswith("_ro") else "write")

c1, c2, c3 = st.columns(3)
with c1: st.metric("Environment", env_name)
with c2: st.metric("Mode", mode)
with c3: st.metric("Database host", (_pghost.split(".supabase.co")[0] + ".supabase.co") if _pghost else "—")

st.divider()

# Friendly guard for read-only deployments
is_readonly = (mode != "write") or _pguser.endswith("_ro")
if is_readonly:
    st.info("This deployment is read-only. You can explore data and print labels.")
else:
    st.success("Uploads and edits are enabled in this deployment.")
