import streamlit as st

st.set_page_config(page_title="CARP", layout="wide")
st.title("CARP — Streamlit UI")

st.markdown("""
Use the **pages** in the sidebar:

- **Overview**: KPIs and counts by (type, code)
- **Details**: Filterable table with downloads
- **Assign & Labels**: Select fish by batch, assign tanks, export labels
""")

st.caption("Tip: set DB connection strings in `.streamlit/secrets.toml` under `[local]` and `[staging]`.")
