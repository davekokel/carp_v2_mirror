import socket, streamlit as st
host = "db.gzmbxhkckkspnefpxkgb.supabase.co"
st.title("DNS Probe (A records)")
try:
    addrs = [ai[4][0] for ai in socket.getaddrinfo(host, 5432, socket.AF_INET)]
    seen = []
    for a in addrs:
        if a not in seen:
            seen.append(a)
    st.code("\n".join(seen) or "<no IPv4>")
except Exception as e:
    st.error(str(e))
