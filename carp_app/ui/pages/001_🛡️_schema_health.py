from __future__ import annotations
import sys, pathlib, os
import pandas as pd
import streamlit as st
from sqlalchemy import text

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.lib.db import get_engine as _create_engine

sb, session, user = require_auth()
require_email_otp()

@st.cache_resource(show_spinner=False)
def _eng():
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

st.set_page_config(page_title="🛡️ Schema Health", page_icon="🛡️", layout="wide")
st.title("🛡️ Schema Health")

# Load contract
contract_path = ROOT / "supabase" / "schema_contract.txt"
if not contract_path.exists():
    st.error(f"Contract file not found: {contract_path}")
    st.stop()

with contract_path.open() as f:
    raw_lines = f.readlines()

def _norm(s: str) -> str:
    return (s or "").split("#", 1)[0].strip()

lines = [_norm(l) for l in raw_lines]
lines = [l for l in lines if l]
soft_mode = False
entries: list[tuple[str,str]] = []
for l in raw_lines:
    if "SOFT" in l:
        soft_mode = True
    obj = _norm(l)
    if not obj:
        continue
    entries.append(("SOFT" if soft_mode else "HARD", obj))

def _check_relation(cx, rel: str) -> bool:
    name = rel.split(".",1)[1]
    q = text("""
      select 1
      from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where n.nspname='public' and c.relname=:rel
      limit 1
    """)
    return bool(cx.execute(q, {"rel": name}).scalar())

def _norm_types(s: str) -> str:
    return (
        (s or "")
        .lower()
        .replace(" ", "")
        .replace("int4", "integer")
        .replace("int", "integer")
        .replace("bool", "boolean")
    )

def _check_function(cx, fn_sig: str) -> bool:
    name, args = fn_sig.split("(",1)
    name = name.split(".",1)[1]
    want = _norm_types(args[:-1])  # drop ')'
    q = text("""
      select oidvectortypes(p.proargtypes) as argtypes
      from pg_proc p join pg_namespace n on n.oid=p.pronamespace
      where n.nspname='public' and p.proname=:name
    """)
    found = False
    for (argtypes,) in cx.execute(q, {"name": name}):
        got = _norm_types(argtypes)
        if (not want and not got) or (want == got):
            found = True
            break
    return found

def _check_trigger(cx, spec: str) -> bool:
    # "schema.table  trigger_name"
    tbl, trg = spec.split()
    q = text("""
      select 1 from pg_trigger t
      where t.tgname=:tg and t.tgrelid=:tbl::regclass
      limit 1
    """)
    return bool(cx.execute(q, {"tg": trg, "tbl": tbl}).scalar())

rows = []
with _eng().begin() as cx:
    for strictness, item in entries:
        if "(" in item and item.endswith(")"):
            ok = _check_function(cx, item); kind = "function"
        elif " " in item and item.startswith("public."):
            ok = _check_trigger(cx, item);  kind = "trigger"
        else:
            ok = _check_relation(cx, item); kind = "relation"
        rows.append({"object": item, "kind": kind, "strict": strictness, "status": "✅" if ok else ("⚠️" if strictness=="SOFT" else "❌")})

df = pd.DataFrame(rows)
c1, c2 = st.columns([2,1])
with c1:
    st.dataframe(df, use_container_width=True, hide_index=True)
with c2:
    st.metric("Hard OK", int((df["strict"]=="HARD").sum() - (df.query("strict=='HARD' and status=='❌'").shape[0])))
    st.metric("Hard Missing", int(df.query("strict=='HARD' and status=='❌'").shape[0]))
    st.metric("Soft Missing", int(df.query("strict=='SOFT' and status=='⚠️'").shape[0]))

missing_hard = df.query("strict=='HARD' and status=='❌'")
if not missing_hard.empty:
    st.error("Contract violations (HARD missing):")
    st.dataframe(missing_hard, use_container_width=True, hide_index=True)

st.caption(f"Contract file: `{contract_path}` — edit via PR to add/retire objects.")