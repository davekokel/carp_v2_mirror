# lib/schema.py
import streamlit as st
from sqlalchemy import text

# ... your ENSURE_TANK_SCHEMA_SQL stays as-is ...

def ensure_tank_schema(cx):
    # Only run schema changes if explicitly enabled
    if not bool(st.secrets.get("ALLOW_SCHEMA_MIGRATIONS", False)):
        return
    try:
        cx.execute(text(ENSURE_TANK_SCHEMA_SQL))
    except Exception as e:
        # Surface the real error for diagnosis
        import streamlit as st
        st.error("Schema ensure failed")
        st.code(str(e))
        raise