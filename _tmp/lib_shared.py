import re
from typing import Dict, List, Optional, Tuple
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

st.set_page_config(page_title="CARP UI", layout="wide")

def pick_environment() -> Tuple[str, str]:
    opts = {
        "Local": st.secrets["local"]["conn"],
        "Staging": st.secrets["staging"]["conn"],
    }
    env = st.sidebar.radio("Environment", list(opts.keys()), index=0)
    return env, opts[env]

@st.cache_resource(show_spinner=False)
def get_engine(conn_str: str) -> Engine:
    return create_engine(conn_str, pool_pre_ping=True)

def parse_query(q: str) -> Dict:
    """
    Parse a mini boolean syntax:
      - terms: alpha/num and _-.
      - AND, OR (case-insensitive)
      - quotes for phrases "foo bar"
    Returns a dict with 'mode' ('AND' or 'OR') and 'terms' list.
    Empty query => AND with empty list.
    """
    if not q or not q.strip():
        return {"mode": "AND", "terms": []}
    # Tokenize quoted phrases or bare words
    tokens = re.findall(r'"([^"]+)"|(\S+)', q)
    raw = [t[0] or t[1] for t in tokens]
    mode = "AND"
    terms: List[str] = []
    for t in raw:
        if t.upper() == "OR":
            mode = "OR"
        elif t.upper() == "AND":
            continue
        else:
            terms.append(t)
    return {"mode": mode, "terms": terms}
