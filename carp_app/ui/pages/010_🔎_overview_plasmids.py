from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os, shlex
from typing import List, Dict, Any, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.lib.db import get_engine

sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="CARP — Plasmids Overview", page_icon="🧪", layout="wide")
st.title("🧪 Plasmids Overview")

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

_ENGINE: Optional[Engine] = None
def _get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        url = os.getenv("DB_URL") or ""
        if not url:
            raise RuntimeError("DB_URL is not set")
        _ENGINE = get_engine()
    return _ENGINE

def _fn_exists(schema: str, name: str) -> bool:
    with _get_engine().begin() as cx:
        return bool(cx.execute(text("""
            select exists(
              select 1
              from pg_proc p
              join pg_namespace n on n.oid = p.pronamespace
              where n.nspname=:s and p.proname=:n
            )
        """), {"s": schema, "n": name}).scalar())

def _build_query(q: str, supports_only: bool, limit: int) -> tuple[str, Dict[str, Any]]:
    # Discover actual column names in public.v_plasmids_rich at runtime
    with _get_engine().begin() as cx:
        cols = pd.read_sql(
            text("""
                select column_name
                from information_schema.columns
                where table_schema='public' and table_name='v_plasmids_rich'
            """),
            cx
        )["column_name"].str.lower().tolist()

    # Helper to pick the first existing column from candidates; otherwise return a SQL literal
    def pick(cands: list[str], if_missing_literal: str = "''") -> str:
        for c in cands:
            if c.lower() in cols:
                return f"r.{c}"
        return if_missing_literal  # safe literal (already quoted)

    # Canonical names (prefer new; fall back to old)
    code_col     = pick(["code", "plasmid_code"])
    name_col     = pick(["name", "plasmid_name"])
    nick_col     = pick(["nickname"])             # nickname typically exists
    fluor_col    = pick(["fluor_names", "fluors"])
    tag_col      = pick(["tag_names", "tags"])
    fusion_col   = pick(["fusion_names", "fusions"])
    resist_col   = pick(["resistance"])
    supp_col     = pick(["supports_invitro_rna"])
    notes_col    = pick(["notes"])
    created_by_c = pick(["created_by"])
    created_at_c = pick(["created_at"])

    # Build haystack & field map based on discovered columns
    haystack = (
        "concat_ws(' ', "
        f"coalesce({code_col},''), coalesce({name_col},''), coalesce({nick_col},''), "
        f"coalesce({fluor_col},''), coalesce({tag_col},''), coalesce({fusion_col},''), "
        f"coalesce({resist_col},''), coalesce({notes_col},''))"
    )

    field_map = {
        "code":       code_col,
        "name":       name_col,
        "nickname":   f"coalesce(p.nickname, {nick_col})",
        "fluors":     f"coalesce({fluor_col},'')",
        "tags":       f"coalesce({tag_col},'')",
        "fusions":    f"coalesce({fusion_col},'')",
        "resistance": f"coalesce(p.resistance, {resist_col})",
    }

    # Parse search tokens
    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    params: Dict[str, Any] = {"lim": int(limit)}
    where: list[str] = []
    for i, tok in enumerate(tokens):
        neg = tok.startswith("-")
        core = tok[1:] if neg else tok
        if ":" in core:
            k, vval = core.split(":", 1)
            k = (k or "").lower()
            vval = (vval or "").strip().strip('"')
            if k in field_map:
                key = f"t{i}"; params[key] = f"%{vval}%"
                where.append(("NOT " if neg else "") + f"({field_map[k]} ILIKE :{key})")
                continue
        key = f"t{i}"; params[key] = f"%{core}%"
        where.append(("NOT " if neg else "") + f"({haystack} ILIKE :{key})")

    if supports_only:
        where.append(f"(coalesce(p.supports_invitro_rna, {supp_col}) = true)")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    # Build SQL using detected column names; join by code
    sql = f"""
      with rich as (
        select
          {code_col}   as code,
          {name_col}   as name,
          {nick_col}   as nickname,
          {fluor_col}  as fluor_names,
          {tag_col}    as tag_names,
          {fusion_col} as fusion_names,
          {resist_col} as resistance,
          {supp_col}   as supports_invitro_rna,
          {notes_col}  as notes,
          {created_by_c} as created_by,
          {created_at_c} as created_at
        from public.v_plasmids_rich r
      )
      select
        r.code                                                as code,
        r.name                                                as name,
        coalesce(p.nickname, r.nickname)                      as nickname,
        coalesce(r.fluor_names,  '')                          as fluor_names,
        coalesce(r.tag_names,    '')                          as tag_names,
        coalesce(r.fusion_names, '')                          as fusion_names,
        coalesce(p.resistance, r.resistance)                  as resistance,
        coalesce(p.supports_invitro_rna, r.supports_invitro_rna) as supports_invitro_rna,
        p.created_by                                          as created_by,
        p.created_at                                          as created_at,
        NULL::uuid                                            as rna_id,
        NULL::text                                            as rna_code,
        NULL::text                                            as rna_name,
        coalesce(p.notes, r.notes)                            as notes
      from rich r
      left join public.plasmids p
        on p.code = r.code
      {where_sql}
      order by r.code
      limit :lim
    """
    return sql, params

def _load_plasmids(q: str, supports_only: bool, limit: int) -> pd.DataFrame:
    sql, params = _build_query(q, supports_only, limit)
    with _get_engine().begin() as cx:
        return pd.read_sql(text(sql), cx, params=params)

with st.form("filters"):
    c1, c2, c3 = st.columns([2,2,1])
    with c1:
        q = st.text_input("Search (supports code:, name:, nickname:, fluors:, tags:, fusions:, resistance:)", "")
    with c2:
        supports_only = st.checkbox("Supports in-vitro RNA only", value=False)
    with c3:
        limit = int(st.number_input("Limit", min_value=1, max_value=10000, value=1000, step=200))
    submitted = st.form_submit_button("Apply")

try:
    df = _load_plasmids(q, supports_only, limit)
except Exception as e:
    st.error(f"Query error: {type(e).__name__}: {e}")
    with st.expander("Debug"):
        st.code(str(e))
    st.stop()

st.caption(f"{len(df)} rows")

for c in [
    "code","name","nickname","fluor_names","tag_names","fusion_names",
    "resistance","supports_invitro_rna","rna_code","rna_name",
    "created_by","created_at","notes"
]:
    if c not in df.columns:
        df[c] = None

view_cols = [
    "✓ Select",
    "code","name","nickname","fluor_names","tag_names","fusion_names",
    "resistance","supports_invitro_rna",
    "rna_code","rna_name","created_by","created_at","notes"
]
df_view = df.copy()
df_view.insert(0, "✓ Select", False)

sig = "|".join(df_view.get("code", pd.Series([], dtype=str)).astype(str).tolist())
if st.session_state.get("_plasmids_sig") != sig:
    st.session_state["_plasmids_sig"] = sig
    st.session_state["_plasmids_table"] = df_view.copy()

edited = st.data_editor(
    st.session_state["_plasmids_table"],
    width="stretch",
    hide_index=True,
    column_order=view_cols,
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
        "code": st.column_config.TextColumn("code", disabled=True),
        "name": st.column_config.TextColumn("name", disabled=True),
        "nickname": st.column_config.TextColumn("nickname", disabled=True),
        "fluor_names": st.column_config.TextColumn("fluors", disabled=True),
        "tag_names": st.column_config.TextColumn("tags", disabled=True),
        "fusion_names": st.column_config.TextColumn("fusions", disabled=True),
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

st.divider()
st.subheader("Actions")

cA, cB, cC = st.columns([1,2,2])
with cA:
    sel_codes = edited.loc[edited["✓ Select"], "code"].dropna().astype(str).tolist()
    st.caption(f"Selected: {len(sel_codes)}")

has_ensure = _fn_exists("public", "ensure_rna_for_plasmid")

with cB:
    ensure_selected = st.button(
        "Ensure RNA for selected",
        disabled=(len(sel_codes) == 0 or not has_ensure),
        use_container_width=True,
    )
with cC:
    ensure_missing_for_supported = st.button(
        "Ensure RNA for all supported (missing only)",
        use_container_width=True,
        help="Create RNAs for all rows where supports_invitro_rna is TRUE but rna_code is empty.",
        disabled=(not has_ensure),
    )

if not has_ensure:
    st.info("ensure_rna_for_plasmid() not installed in this DB; actions are disabled.")

sql_ensure = text("select * from public.ensure_rna_for_plasmid(:plasmid_code, 'RNA', :rna_name, :by, :notes)")
user_by = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"

if has_ensure and ensure_selected:
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

if has_ensure and ensure_missing_for_supported:
    ok = 0
    miss_df = edited[
        (edited["supports_invitro_rna"] == True)
        & (edited["rna_code"].isna() | (edited["rna_code"] == ""))
    ]
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