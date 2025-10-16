from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
from carp_app.lib.config import engine as get_engine, DB_URL
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os, shlex
from typing import List, Dict, Any
import pandas as pd
import streamlit as st
from carp_app.lib.db import get_engine
from sqlalchemy import text
# ---- page config FIRST ----
st.set_page_config(page_title="CARP — Plasmids Overview", page_icon="🧪", layout="wide")
st.title("🧪 Plasmids Overview")

# ---- optional unlock ----
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# ---- engine ----
_ENGINE = None
def _get_engine():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL is not set")
    _ENGINE = get_engine()
    return _ENGINE

# ---- query helpers (reads vw_plasmids_overview) ----
def _build_query(q: str, supports_only: bool) -> tuple[str, Dict[str, Any]]:
    """
    Multi-term AND search with field filters:
      code:, name:, nickname:, fluors:, resistance:
    """
    haystack = (
        "concat_ws(' ', "
        "coalesce(v.code,''), coalesce(v.name,''), coalesce(v.nickname,''), "
        "coalesce(v.fluors,''), coalesce(v.resistance,''), coalesce(v.notes,''))"
    )

    field_map = {
        "code": "v.code",
        "name": "v.name",
        "nickname": "v.nickname",
        "fluors": "v.fluors",
        "resistance": "v.resistance",
    }

    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    params: Dict[str, Any] = {}
    where: List[str] = []

    for i, tok in enumerate(tokens):
        neg = tok.startswith("-")
        core = tok[1:] if neg else tok

        k = vval = None
        if ":" in core:
            k, vval = core.split(":", 1)
            k = (k or "").strip().lower()
            vval = (vval or "").strip().strip('"')

        if k in field_map and vval is not None:
            key = f"t{i}"
            params[key] = f"%{vval}%"
            clause = f"{field_map[k]} ILIKE :{key}"
            where.append(("NOT " if neg else "") + f"({clause})")
        else:
            key = f"t{i}"
            params[key] = f"%{core}%"
            clause = f"{haystack} ILIKE :{key}"
            where.append(("NOT " if neg else "") + f"({clause})")

    if supports_only:
        where.append("v.supports_invitro_rna = true")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
      select
        v.id,
        v.code,
        v.name,
        v.nickname,
        v.fluors,
        v.resistance,
        v.supports_invitro_rna,
        v.created_by,
        v.notes,
        v.created_at,
        v.rna_id,
        v.rna_code,
        v.rna_name
      from public.vw_plasmids_overview v
      {where_sql}
      order by v.code
    """
    return sql, params

def _load_plasmids(q: str, supports_only: bool, limit: int) -> pd.DataFrame:
    sql, params = _build_query(q, supports_only)
    with _get_engine().begin() as cx:
        df = pd.read_sql(text(sql), cx, params=params)
    if limit and isinstance(limit, int) and limit > 0:
        df = df.head(limit)
    return df

# ---- filters ----
with st.form("filters"):
    c1, c2, c3 = st.columns([2,2,1])
    with c1:
        q = st.text_input("Search plasmids (multi-term; field filters like code:, name:, resistance:)", "")
    with c2:
        supports_only = st.checkbox("Supports in-vitro RNA only", value=False)
    with c3:
        limit = int(st.number_input("Limit", min_value=1, max_value=10000, value=1000, step=200))
    submitted = st.form_submit_button("Apply")

# ---- load ----
df = _load_plasmids(q, supports_only, limit)
st.caption(f"{len(df)} rows")

# ---- render with selection + bulk actions ----
for c in [
    "code","name","nickname","fluors","resistance","supports_invitro_rna",
    "rna_code","rna_name","created_by","created_at","notes"
]:
    if c not in df.columns:
        df[c] = None

view_cols = [
    "✓ Select",
    "code","name","nickname","fluors","resistance","supports_invitro_rna",
    "rna_code","rna_name","created_by","created_at","notes"
]

df_view = df.copy()
df_view.insert(0, "✓ Select", False)

# persist table state across edits
sig = "|".join(df_view.get("code", pd.Series([], dtype=str)).astype(str).tolist())
if st.session_state.get("_plasmids_sig") != sig:
    st.session_state["_plasmids_sig"] = sig
    st.session_state["_plasmids_table"] = df_view.copy()

edited = st.data_editor(
    st.session_state["_plasmids_table"],
    use_container_width=True,
    hide_index=True,
    column_order=view_cols,
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
        "code": st.column_config.TextColumn("code", disabled=True),
        "name": st.column_config.TextColumn("name", disabled=True),
        "nickname": st.column_config.TextColumn("nickname", disabled=True),
        "fluors": st.column_config.TextColumn("fluors", disabled=True),
        "resistance": st.column_config.TextColumn("resistance", disabled=True),
        "supports_invitro_rna": st.column_config.CheckboxColumn("supports_invitro_rna", disabled=True),
        "rna_code": st.column_config.TextColumn("rna_code", disabled=True),
        "rna_name": st.column_config.TextColumn("rna_name", disabled=True),
        "created_by": st.column_config.TextColumn("created_by", disabled=True),
        "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
        "notes": st.column_config.TextColumn("notes", disabled=True),
    },
    key="plasmids_editor",
)
st.session_state["_plasmids_table"] = edited.copy()

# ---- actions ----
st.divider()
st.subheader("Actions")

cA, cB, cC = st.columns([1,2,2])
with cA:
    sel_codes = edited.loc[edited["✓ Select"], "code"].dropna().astype(str).tolist()
    st.caption(f"Selected: {len(sel_codes)}")
with cB:
    ensure_selected = st.button("Ensure RNA for selected", disabled=len(sel_codes)==0, use_container_width=True)
with cC:
    ensure_missing_for_supported = st.button(
        "Ensure RNA for all supported (missing only)",
        use_container_width=True,
        help="Create RNAs for all rows where supports_invitro_rna is TRUE but rna_code is empty."
    )

sql_ensure = text("select * from public.ensure_rna_for_plasmid(:plasmid_code, 'RNA', :rna_name, :by, :notes)")
user_by = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"

if ensure_selected:
    ok = fail = 0
    with _get_engine().begin() as cx:
        for code, name in edited.loc[edited["✓ Select"], ["code","name"]].itertuples(index=False):
            try:
                cx.execute(sql_ensure, {
                    "plasmid_code": code,
                    "rna_name": (name or f"{code}RNA"),
                    "by": user_by,
                    "notes": None,
                })
                ok += 1
            except Exception as e:
                fail += 1
                st.error(f"{code}: {e}")
    st.success(f"Ensured RNAs for {ok} code(s). Failures: {fail}. Click Apply to refresh.")

if ensure_missing_for_supported:
    ok = 0
    miss_df = edited[(edited["supports_invitro_rna"] == True) & (edited["rna_code"].isna() | (edited["rna_code"]==""))]
    with _get_engine().begin() as cx:
        for code, name in miss_df[["code","name"]].itertuples(index=False):
            try:
                cx.execute(sql_ensure, {
                    "plasmid_code": code,
                    "rna_name": (name or f"{code}RNA"),
                    "by": user_by,
                    "notes": None,
                })
                ok += 1
            except Exception as e:
                st.error(f"{code}: {e}")
    st.success(f"Ensured RNAs for {ok} supported plasmid(s) without RNAs. Click Apply to refresh.")
