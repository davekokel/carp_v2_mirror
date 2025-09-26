import streamlit as st
st.set_page_config(page_title="CARP health", layout="wide")
st.success("✅ UI is rendering")
st.write("ENV:", st.secrets.get("ENV_NAME", "(unset)"))
st.write("has CONN:", bool(st.secrets.get("CONN")))