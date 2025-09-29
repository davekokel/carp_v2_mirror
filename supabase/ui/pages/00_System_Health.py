from lib.page_bootstrap import secure_page; secure_page()

import streamlit as st
from lib.authz import require_app_access, logout_button
from lib.db import get_engine
from lib.health import render_health_panel

st.set_page_config(page_title="System Health", layout="wide")
require_app_access("🔐 CARP — Private")
logout_button("sidebar", key="logout_btn_health")

_engine = get_engine()
render_health_panel(_engine)
