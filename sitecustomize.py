# Auto-run on every Streamlit page/module import
# (Python imports `sitecustomize` automatically if present on sys.path)
try:
    import streamlit as st
    from lib.page_bootstrap import secure_page
    # Only attempt UI gating when Streamlit is actually running a script
    # If anything looks off (e.g., CLI tools, non-Streamlit context), fail quietly.
    secure_page()
except Exception:
    pass
