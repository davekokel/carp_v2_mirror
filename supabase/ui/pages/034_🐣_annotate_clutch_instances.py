# 034_🐣_annotate_clutch_instances.py
from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    try:
        from auth_gate import require_app_unlock
    except Exception:
        def require_app_unlock(): ...
require_app_unlock()

import os
from datetime import date, timedelta
from typing import List

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _ensure_sslmode(url: str) -> str:
    from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
    u = urlparse(url)
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    host = (u.hostname or "").lower() if u.hostname else ""
    if host in {"localhost", "127.0.0.1", "::1"}:
        q["sslmode"] = "disable"
    else:
        q.setdefault("sslmode", "require")
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))

@st.cache_resource(show_spinner=False)
def _get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        st.stop()
    return create_engine(_ensure_sslmode(url))

ENGINE = _get_engine()

st.set_page_config(page_title="Annotate Clutch Instances", page_icon="🐣")
st.title("🐣 Annotate Clutch Instances")

# -----------------------------
# Sidebar filters
# -----------------------------
with st.sidebar:
    st.header("Filters")
    q = st.text_input("Search code / note / created_by")
    days = st.number_input("Look back (days)", min_value=0, value=14, step=1)
    start = date.today() - timedelta(days=int(days))
    end = date.today()

# -----------------------------
# Helper: which columns exist?
# -----------------------------
def _existing_cols() -> List[str]:
    with ENGINE.connect() as cx:
        cols = pd.read_sql(
            text("""
                select column_name
                from information_schema.columns
                where table_schema='public' and table_name='clutch_containers'
            """),
            cx,
        )["column_name"].tolist()
    return cols

cols = _existing_cols()
has = {c: c in cols for c in ["id","id_uuid","clutch_id","clutch_instance_code","clutch_size","description","notes","created_by","created_at"]}

# pick a pk-ish column
pk_col = "id_uuid" if has["id_uuid"] else ("id" if has["id"] else None)
if pk_col is None:
    st.error("clutch_containers must have id or id_uuid column.")
    st.stop()

# -----------------------------
# Load instances (recent)
# -----------------------------
with ENGINE.connect() as cx:
    df = pd.read_sql(
        text(f"""
            select
              {pk_col}::text as container_id,
              {"clutch_instance_code" if has["clutch_instance_code"] else "null::text as clutch_instance_code"},
              {"clutch_id" if has["clutch_id"] else "null::uuid as clutch_id"},
              {"clutch_size" if has["clutch_size"] else "null::int as clutch_size"},
              {"description" if has["description"] else "null::text as description"},
              {"notes" if has["notes"] else "null::text as notes"},
              {"created_by" if has["created_by"] else "null::text as created_by"},
              {"created_at" if has["created_at"] else "now() as created_at"}
            from public.clutch_containers
            where (created_at::date between :dmin and :dmax)
            order by created_at desc
        """),
        cx,
        params={"dmin": start, "dmax": end},
    )

# Apply text filter
if q:
    ql = q.lower()
    def contains(s: pd.Series) -> pd.Series:
        return s.astype(str).str.lower().str.contains(ql, na=False)
    mask = (
        contains(df.get("clutch_instance_code", pd.Series(index=df.index, dtype=str))) |
        contains(df.get("notes", pd.Series(index=df.index, dtype=str))) |
        contains(df.get("description", pd.Series(index=df.index, dtype=str))) |
        contains(df.get("created_by", pd.Series(index=df.index, dtype=str)))
    )
    df = df[mask]

# -----------------------------
# Checkbox table (master)
# -----------------------------
view_cols = [c for c in [
    "clutch_instance_code",
    "clutch_size",
    "description",
    "notes",
    "created_by",
    "created_at",
] if c in df.columns]

if df.empty:
    st.info("No clutch instances found for the current filters.")
    st.stop()

df_view = df[view_cols + ["container_id"]].copy()
df_view = df_view.set_index("container_id", drop=True)
df_view.index = df_view.index.map(str)
df_view.insert(0, "✅", False)

edited = st.data_editor(
    df_view,
    hide_index=True,
    use_container_width=True,
    column_config={
        "✅": st.column_config.CheckboxColumn(help="Select instances to save updates"),
        "clutch_size": st.column_config.NumberColumn(step=1, min_value=0),
    },
    key="clutch_instances_editor",
)

selected_ids = edited.index[edited["✅"] == True].tolist()

st.divider()
st.subheader(f"Save {len(selected_ids)} selected instance(s)")

save = st.button("💾 Save selected")
if save:
    if not selected_ids:
        st.warning("Select at least one instance.")
    else:
        # Build updates only for editable columns that actually exist
        updatable = [c for c in ["clutch_size","description","notes"] if c in df_view.columns and has.get(c, False)]
        if not updatable:
            st.error("No editable columns (clutch_size, description, notes) exist on clutch_containers.")
            st.stop()
        # Prepare parameterized updates
        try:
            with ENGINE.begin() as cx:
                for cid in selected_ids:
                    row = edited.loc[cid]
                    sets = []
                    params = {"cid": cid}
                    for c in updatable:
                        sets.append(f"{c} = :{c}")
                        params[c] = None if pd.isna(row.get(c)) else row.get(c)
                    sql = text(f"update public.clutch_containers set {', '.join(sets)} where {pk_col}::text = :cid")
                    cx.execute(sql, params)
            st.success(f"Saved {len(selected_ids)} instance(s).")
        except Exception as e:
            st.error(f"Failed to save: {e}")

st.caption("Tip: If columns are missing, add them to public.clutch_containers and reload.")