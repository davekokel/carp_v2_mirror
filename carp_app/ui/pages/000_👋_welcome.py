from __future__ import annotations
import os, re, sys
import streamlit as st

# Gate auth: only import when AUTH_MODE=on
AUTH_MODE = os.getenv("AUTH_MODE", "off").lower()
if AUTH_MODE == "on":
    from carp_app.ui.auth_gate import require_auth
    sb, session, user = require_auth()
else:
    sb = session = user = None

st.set_page_config(page_title="CARP — Welcome", page_icon="👋", layout="wide")

from carp_app.ui.lib.env_badge import show_env_badge, _env_from_db_url
from carp_app.lib.secret import env_info
from carp_app.lib.config import DB_URL, AUTH_MODE, env_name

st.title("👋 Welcome to CARP")
show_env_badge()
_env,_proj,_host,_mode = env_info()
import os, streamlit as st
from carp_app.lib.secret import get_secret
# st.caption('RAW_DB_URL: ' + os.getenv('DB_URL','(missing)'))
st.write("Browse live data, upload CSVs, and print labels — no install needed. Use the **left sidebar** to navigate.")


# Compact status (derived from DB_URL)
import re
DB_URL = os.getenv("DB_URL","")
m = re.match(r".*://([^:@]+)@([^/?]+)", DB_URL)
_pguser = m.group(1) if m else os.getenv("PGUSER","")
_pghost = m.group(2) if m else os.getenv("PGHOST","")
_proj   = _pguser.split(".",1)[1] if "." in _pguser else "?"

from carp_app.ui.lib.env_badge import _env_from_db_url
_env, _proj, _host = _env_from_db_url(DB_URL)
env_name = _env
_pghost = _host
mode = os.getenv("APP_MODE") or ("readonly" if _pguser.endswith("_ro") else "write")

c1, c2, c3 = st.columns(3)
with c1: st.metric("Environment", env_name)
with c2: st.metric("Mode", _mode)
with c3: st.metric("Database host", _host if _host else "—")

st.divider()

# Friendly guard for read-only deployments
is_readonly = (mode != "write") or _pguser.endswith("_ro")
if is_readonly:
    st.info("This deployment is read-only. You can explore data and print labels.")
else:
    st.success("Uploads and edits are enabled in this deployment.")
