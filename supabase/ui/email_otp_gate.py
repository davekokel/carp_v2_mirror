# supabase/ui/email_otp_gate.py
from __future__ import annotations
import streamlit as st

st.sidebar.write("✅ loaded gate version: SHORT RETURN")

def require_email_otp():
    return  # TEMP: bypass auth entirely while debugging