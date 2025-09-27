# health.py
from lib.authz import require_app_access
require_app_access("🔐 CARP — Private")
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Health", layout="wide")
st.success("✅ Streamlit rendered")
st.write("Python:", sys.version.split()[0], "| Platform:", platform.platform())
st.write("Repo files:", ", ".join(sorted(p for p in os.listdir('.') if not p.startswith('.'))))

c1, c2, c3 = st.columns(3)
with c1: st.metric("has CONN_DIRECT", bool(st.secrets.get("CONN_DIRECT")))
with c2: st.metric("has CONN_POOL", bool(st.secrets.get("CONN_POOL")))
with c3: st.metric("ENV_NAME", st.secrets.get("ENV_NAME", "(unset)"))

st.title("DB health")

def mask_pwd(url: str) -> str:
    pwd = st.secrets.get("PGPASSWORD")  # may be None if using DSN
    if pwd:
        return url.replace(pwd, "********")
    # fallback mask: hide anything between first ":" after scheme and "@"
    try:
        scheme, rest = url.split("://", 1)
        if "@" in rest and ":" in rest.split("@", 1)[0]:
            user, tail = rest.split("@", 1)[0], rest.split("@", 1)[1]
            u, p = user.split(":", 1)
            return f"{scheme}://{u}:********@{tail}"
    except Exception:
        pass
    return url

def try_connect(url: str, label: str):
    st.subheader(f"Try {label}")
    st.code(mask_pwd(url), language="text")
    try:
        eng = create_engine(
            url,
            pool_pre_ping=True,
            future=True,
            connect_args={"prepare_threshold": None},  # safe for PgBouncer, harmless direct
        )
        t0 = time.time()
        with eng.connect() as cx:
            who = cx.execute(text("select current_user")).scalar()
            ver = cx.execute(text("select version()")).scalar()
        st.success(f"OK as {who} · {ver.split()[0]}  (%.2fs)" % (time.time() - t0))
        return True
    except Exception as e:
        st.error("Connect failed")
        st.code(str(e))
        return False

direct = st.secrets.get("CONN_DIRECT")
pooler = st.secrets.get("CONN_POOL")

if not (direct or pooler):
    st.warning("Add CONN_DIRECT and/or CONN_POOL to Secrets.")
else:
    ok = False
    if direct:
        ok = try_connect(direct, "DIRECT (5432)")
    if (not ok) and pooler:
        try_connect(pooler, "POOLER (6543)")
