# carp_app/ui/pages/009_📤_upload_plasmids_overview.py
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

def _build_query(q: str, supports_only: bool, limit: int) -> tuple[str, dict]:
    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    params: dict = {"lim": int(limit)}
    where: list[str] = []

    # search targets (we'll select these aliases below)
    field_map = {
        "code":       "p.code",
        "name":       "p.name",
        "nickname":   "p.nickname",
        "fluors":     "COALESCE(a.fluor_names,'')",
        "tags":       "COALESCE(a.tag_names,'')",
        "fusions":    "COALESCE(a.fusion_names,'')",
        "resistance": "p.resistance",
        "notes":      "p.notes",
    }
    haystack = (
        "concat_ws(' ', "
        "coalesce(p.code,''), coalesce(p.name,''), coalesce(p.nickname,''), "
        "coalesce(a.fluor_names,''), coalesce(a.tag_names,''), coalesce(a.fusion_names,''), "
        "coalesce(p.resistance,''), coalesce(p.notes,''))"
    )

    for i, tok in enumerate(tokens):
        neg = tok.startswith("-")
        core = tok[1:] if neg else tok
        if ":" in core:
            k, v = core.split(":", 1)
            k = (k or "").lower()
            v = (v or "").strip().strip('"')
            if k in field_map:
                key = f"t{i}"
                params[key] = f"%{v}%"
                where.append(("NOT " if neg else "") + f"({field_map[k]} ILIKE :{key})")
                continue
        key = f"t{i}"
        params[key] = f"%{core}%"
        where.append(("NOT " if neg else "") + f"({haystack} ILIKE :{key})")

    if supports_only:
        where.append("(p.supports_invitro_rna = true)")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
      WITH agg AS (
        SELECT
          p.code,
          COALESCE(string_agg(DISTINCT fl.fluor_name, '; ' ORDER BY fl.fluor_name), '') AS fluor_names,
          COALESCE(string_agg(DISTINCT tg.tag_name,   '; ' ORDER BY tg.tag_name),   '') AS tag_names,
          COALESCE(string_agg(
            DISTINCT CASE
              WHEN fu.tag_id IS NOT NULL AND fu.fluor_id IS NOT NULL THEN tg.tag_name||'::'||fl.fluor_name
              WHEN fu.tag_id IS NOT NULL THEN tg.tag_name
              WHEN fu.fluor_id IS NOT NULL THEN fl.fluor_name
            END, '; ' ORDER BY
              CASE
                WHEN fu.tag_id IS NOT NULL AND fu.fluor_id IS NOT NULL THEN tg.tag_name||'::'||fl.fluor_name
                WHEN fu.tag_id IS NOT NULL THEN tg.tag_name
                WHEN fu.fluor_id IS NOT NULL THEN fl.fluor_name
              END
          ), '') AS fusion_names
        FROM public.plasmids p
        LEFT JOIN public.join_plasmid_fusions j ON j.plasmid_id=p.id
        LEFT JOIN public.fusions fu             ON fu.id=j.fusion_id
        LEFT JOIN public.fluors  fl             ON fl.id=fu.fluor_id
        LEFT JOIN public.tags    tg             ON tg.id=fu.tag_id
        GROUP BY p.code
      )
      SELECT
        p.code,
        p.name,
        p.nickname,
        a.fluor_names,
        a.tag_names,
        a.fusion_names,
        p.resistance,
        p.supports_invitro_rna,
        p.created_by,
        p.created_at,
        NULL::uuid AS rna_id,
        NULL::text AS rna_code,
        NULL::text AS rna_name,
        p.notes
      FROM public.plasmids p
      LEFT JOIN agg a ON a.code = p.code
      {where_sql}
      ORDER BY p.code
      LIMIT :lim
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

# Ensure display columns exist (use the names we actually selected)
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