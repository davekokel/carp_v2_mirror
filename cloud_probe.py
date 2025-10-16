import os, sys, platform, streamlit as st
st.title("Cloud Probe ✅")
st.write("BOOT: cloud_probe start")
st.write({"python": sys.version, "platform": platform.platform()})
st.write({"DB_URL": os.getenv("DB_URL", "<missing>")[:80] + "…"})
st.write({"AUTH_MODE": os.getenv("AUTH_MODE", "<missing>")})
st.success("If you can see this, the container built and ran your code.")
