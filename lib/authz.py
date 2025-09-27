import streamlit as st

def get_current_user_email() -> str:
    """
    On Streamlit Community Cloud, st.experimental_user is populated.
    Locally (and sometimes on self-hosted), it may be None.
    """
    u = getattr(st, "experimental_user", None)
    if isinstance(u, dict) and "email" in u and u["email"]:
        return u["email"].strip().lower()
    # Fallbacks: allow a local override via secrets or show as anonymous
    return (st.secrets.get("local_dev_email", "") or "").strip().lower()

def is_admin(email: str) -> bool:
    admins = [e.strip().lower() for e in st.secrets.get("admins", [])]
    return bool(email and email in admins)

def is_pilot(email: str) -> bool:
    pilots = [e.strip().lower() for e in st.secrets.get("pilot_emails", [])]
    # Admins are automatically pilots
    return is_admin(email) or (email and email in pilots)

def prod_banner(env: str):
    """Adds a visible environment banner."""
    label = "PRODUCTION" if env.lower() == "production" else env.upper()
    st.markdown(
        f"""
<div style="
  position: sticky; top: 0; z-index: 999;
  padding: 8px 12px; margin: -1rem -1rem 1rem -1rem;
  background: {'#d93025' if label=='PRODUCTION' else '#1a73e8'};
  color: white; font-weight: 700; letter-spacing: .04em;">
  {label}
</div>
""",
        unsafe_allow_html=True,
    )