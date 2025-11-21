# carp_app/ui/pages/110_🔎_overview_fusions.py
from __future__ import annotations

import os
import pathlib
import sys
import shlex
from typing import Optional, Dict, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── repo bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock():
        ...

from carp_app.ui.lib.app_ctx import get_engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Fusions Overview",
    page_icon="🧬",
    layout="wide",
)
st.title("🧬 Fusions Overview")

# ───────── engine cache ─────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return get_engine()

# ───────── search helpers ─────────
def _normalize(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None

def _build_query(q: str, limit: int) -> tuple[str, Dict[str, Any]]:
    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    params: Dict[str, Any] = {"lim": int(limit)}
    where = []

    # canonical column names from v_fusions_overview
    c_fluor = "fluor"
    c_tag   = "tag"
    c_pos   = "tag_pos"
    c_name  = "fusion_name"

    field_map = {"fluor": c_fluor, "tag": c_tag, "pos": c_pos, "name": c_name}
    haystack = f"concat_ws(' ', {c_fluor}, {c_tag}, {c_pos}, {c_name})"

    for i, tok in enumerate(tokens):
        neg = tok.startswith("-")
        core = tok[1:] if neg else tok
        if ":" in core:
            k, v = core.split(":", 1)
            k = k.lower().strip()
            v = v.strip().strip('"')
            if k in field_map:
                key = f"p{i}"
                params[key] = f"%{v}%"
                where.append(f"{'NOT ' if neg else ''}{field_map[k]} ILIKE :{key}")
                continue
        key = f"p{i}"
        params[key] = f"%{core}%"
        where.append(f"{'NOT ' if neg else ''}{haystack} ILIKE :{key}")

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    sql = f"""
    SELECT
      id,
      fusion_name,
      fluor,
      tag,
      tag_pos,
      n_plasmids,
      n_rnas,
      created_at
    FROM public.v_fusions_overview
    {where_sql}
    ORDER BY
      n_plasmids DESC,
      n_rnas     DESC,
      fluor,
      tag     NULLS FIRST,
      tag_pos NULLS FIRST
    LIMIT :lim
    """

    return sql, params

# ───────── load fusions ─────────
def _load_fusions(q: str, lim: int) -> pd.DataFrame:
    sql, params = _build_query(q, lim)
    with _eng().begin() as cx:
        df = pd.read_sql(text(sql), cx, params=params)
    for c in df.select_dtypes(include=["object","string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

# ───────── filters ─────────
with st.form("fusion_filters", clear_on_submit=False):
    c1, c2 = st.columns([3,1])
    with c1:
        q_raw = st.text_input(
            "Search (supports fluor:, tag:, pos:, name:, -negation)",
            ""
        )
    with c2:
        limit = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=1500,
                step=100,
            )
        )
    _ = st.form_submit_button("Apply")

q = _normalize(q_raw)

# ───────── fetch data ─────────
try:
    df = _load_fusions(q or "", limit)
except Exception as e:
    st.error(f"Query error: {type(e).__name__}: {e}")
    st.stop()

st.caption(f"{len(df)} fusion(s)")

# ───────── data table ─────────
view = df.copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    key="fusions_overview_v8",
    column_order=[
        "✓ Select", "fusion_name", "fluor", "tag", "tag_pos",
        "n_plasmids", "n_rnas"
    ],
    column_config={
        "✓ Select":    st.column_config.CheckboxColumn("✓", default=False),
        "fusion_name": st.column_config.TextColumn("Fusion", disabled=True),
        "fluor":       st.column_config.TextColumn("Fluor", disabled=True),
        "tag":         st.column_config.TextColumn("Tag", disabled=True),
        "tag_pos":     st.column_config.TextColumn("Pos", disabled=True),
        "n_plasmids":  st.column_config.NumberColumn("Plasmids", disabled=True),
        "n_rnas":      st.column_config.NumberColumn("RNAs", disabled=True),
    },
)

st.divider()

# ───────── plasmid preview for selected fusion ─────────
selected_ids = []
fusion_names = {}

if isinstance(grid, pd.DataFrame) and "✓ Select" in grid.columns:
    sel = grid.loc[grid["✓ Select"] == True]
    if not sel.empty and "id" in sel.columns:
        selected_ids = sel["id"].astype(str).tolist()
        fusion_names = dict(zip(sel["id"].astype(str), sel["fusion_name"]))

if len(selected_ids) == 1:
    fusion_id = selected_ids[0]
    fusion_label = fusion_names.get(fusion_id, fusion_id)

    with _eng().begin() as cx:
        plasmids_df = pd.read_sql(
            text("""
                SELECT
                  p.code,
                  COALESCE(p.name,'')     AS name,
                  COALESCE(p.nickname,'') AS nickname,
                  p.created_at
                FROM public.join_plasmid_fusions jpf
                JOIN public.plasmids p ON p.id = jpf.plasmid_id
                WHERE jpf.fusion_id = :fid
                ORDER BY p.created_at DESC NULLS LAST, p.code
            """),
            cx,
            params={"fid": fusion_id},
        )

    st.subheader(f"Plasmids containing: {fusion_label}")
    if plasmids_df.empty:
        st.info("No plasmids linked to this fusion.")
    else:
        st.dataframe(
            plasmids_df[["code","name","nickname","created_at"]],
            hide_index=True,
            use_container_width=True
        )
        st.download_button(
            "⬇︎ Download plasmids (CSV)",
            data=plasmids_df.to_csv(index=False).encode("utf-8"),
            file_name=f"plasmids_for_fusion_{fusion_label}.csv",
            type="secondary",
        )
elif len(selected_ids) > 1:
    st.info("Select exactly one fusion to preview its plasmids.")
else:
    st.caption("Tip: check a fusion row above to preview its plasmids.")

# ───────── final export ─────────
st.download_button(
    "⬇︎ Download full fusion table (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="fusions_overview.csv",
    type="primary",
    mime="text/csv",
)