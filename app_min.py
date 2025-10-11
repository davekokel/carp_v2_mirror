import os, streamlit as st
st.set_page_config(page_title="Boot check", page_icon="✅")
st.title("Streamlit Cloud Boot Check")
st.write("Python:", os.sys.version)
st.write("APP_ENV:", os.getenv("APP_ENV"))
st.write("DB_URL present:", bool(os.getenv("DB_URL")))
st.success("If you can see this, the service is running.")
