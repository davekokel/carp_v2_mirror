import streamlit as st
from lib import db
import streamlit as st
st.caption("BOOT OK · ENV="+str(st.secrets.get("ENV_NAME","(unset)")))
st.set_page_config(page_title="CARP", layout="wide")
st.title("CARP")
st.write("Use the sidebar to navigate pages.")
