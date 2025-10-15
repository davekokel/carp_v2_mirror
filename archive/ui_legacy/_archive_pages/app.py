import streamlit as st
from lib.authz import require_app_access
require_app_access("🔐 CARP — Private")
st.set_page_config(page_title="ping", layout="wide")
st.title("✅ minimal render check")
st.write("This proves the Python process started and Streamlit rendered.")