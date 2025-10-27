import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1].parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    
import streamlit as st
st.set_page_config(page_title="CARP", page_icon="🐟", layout="wide")
st.title("CARP UI")
st.caption("Use the sidebar to select a page. Pages live in `carp_app/ui/pages/`.")
st.sidebar.success("Select a page above.")
