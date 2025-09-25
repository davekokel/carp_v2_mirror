import streamlit as st

st.set_page_config(page_title="CARP", layout="wide")

# Minimal boot diagnostics
try:
    has_conn = bool(st.secrets.get("CONN"))
    st.caption(f"boot: CONN={has_conn} ENV_NAME={st.secrets.get('ENV_NAME','(none)')}")
except Exception as e:
    st.error(f"secrets not readable: {e}")
    st.stop()

# If you have a gate, temporarily show what it sees:
admins = st.secrets.get("admins", [])
pilots = st.secrets.get("pilot_emails", [])
st.caption(f"auth lists: admins:{len(admins)} pilots:{len(pilots)}")

st.set_page_config(page_title="CARP", layout="wide")
st.title("CARP")
st.write("Use the sidebar to navigate pages.")
