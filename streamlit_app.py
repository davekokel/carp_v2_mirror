# streamlit_app.py
import streamlit as st
from lib.authz import require_app_access, read_only_banner, logout_button

st.set_page_config(page_title="CARP", layout="wide")

# Global gate + banners (applies to all pages)
require_app_access("🔐 CARP — Private")
read_only_banner()
logout_button("sidebar")  # <-- this makes Logout show on every page

# You can add a tiny welcome or leave it empty.
st.write(" ")