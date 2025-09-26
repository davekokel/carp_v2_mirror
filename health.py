import os, sys, platform, streamlit as st
st.set_page_config(page_title="Health", layout="wide")
st.success("✅ Streamlit rendered")
st.write("Python:", sys.version.split()[0], "| Platform:", platform.platform())
st.write("Repo files:", ", ".join(sorted([p for p in os.listdir('.') if not p.startswith('.')])))

c1,c2,c3=st.columns(3)
with c1: st.metric("has CONN", bool(st.secrets.get("CONN")))
with c2: st.metric("has PGHOST", bool(st.secrets.get("PGHOST")))
with c3: st.metric("ENV_NAME", st.secrets.get("ENV_NAME","(unset)"))
