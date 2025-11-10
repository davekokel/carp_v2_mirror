from __future__ import annotations
import sys, pathlib, os, shlex
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="CARP — Fusions Overview", page_icon="🧬", layout="wide")
st.title("🧬 Fusions Overview")

_ENGINE: Engine | None = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        if not os.getenv("DB_URL"): raise RuntimeError("DB_URL not set")
        _ENGINE = get_engine()
    return _ENGINE

def _build_query(q: str, limit: int) -> tuple[str, dict]:
    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    params: dict = {"lim": int(limit)}
    where: list[str] = []

    # computed presentation columns
    c_fluor = "COALESCE(fl.fluor_code,'')"
    c_tag   = "COALESCE(tg.tag_code,'')"
    c_pos   = "COALESCE(f.tag_pos,'')"
    c_name  = "CASE WHEN tg.tag_code IS NULL THEN fl.fluor_code ELSE fl.fluor_code||'::'||tg.tag_code END"

    field_map = {
        "fluor": c_fluor,
        "tag":   c_tag,
        "pos":   c_pos,
        "name":  c_name,
    }
    haystack = f"concat_ws(' ', {c_fluor}, {c_tag}, {c_pos}, {c_name})"

    for i, tok in enumerate(tokens):
        neg = tok.startswith("-")
        core = tok[1:] if neg else tok
        if ":" in core:
            k, v = core.split(":", 1)
            k = k.lower().strip()
            v = v.strip().strip('"')
            if k in field_map:
                key = f"t{i}"
                params[key] = f"%{v}%"
                where.append(("NOT " if neg else "") + f"({field_map[k]} ILIKE :{key})")
                continue
        key = f"t{i}"
        params[key] = f"%{core}%"
        where.append(("NOT " if neg else "") + f"({haystack} ILIKE :{key})")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
      SELECT
        f.id,
        {c_fluor} AS fluor,
        NULLIF({c_tag},'') AS tag,
        NULLIF({c_pos},'') AS tag_pos,
        ({c_name}) AS fusion_name,
        COALESCE(p.n_plasmids,0) AS n_plasmids,
        COALESCE(r.n_rnas,0)     AS n_rnas
      FROM public.fusions f
      LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
      LEFT JOIN public.tags   tg ON tg.id = f.tag_id
      LEFT JOIN (
        SELECT jpf.fusion_id, COUNT(*)::int AS n_plasmids
        FROM public.join_plasmid_fusions jpf
        GROUP BY jpf.fusion_id
      ) p ON p.fusion_id = f.id
      LEFT JOIN (
        SELECT jrf.fusion_id, COUNT(*)::int AS n_rnas
        FROM public.join_rna_fusions jrf
        GROUP BY jrf.fusion_id
      ) r ON r.fusion_id = f.id
      {where_sql}
      ORDER BY n_plasmids DESC, n_rnas DESC, fluor, tag NULLS FIRST, tag_pos NULLS FIRST
      LIMIT :lim
    """
    return sql, params

def _load_fusions(q: str, limit: int) -> pd.DataFrame:
    sql, params = _build_query(q, limit)
    with _eng().begin() as cx:
        return pd.read_sql(text(sql), cx, params=params)

with st.form("filters"):
    c1, c2 = st.columns([3,1])
    with c1:
        q = st.text_input("Search (supports fluor:, tag:, pos:, name:)", "")
    with c2:
        limit = int(st.number_input("Limit", min_value=1, max_value=20000, value=2000, step=500))
    submitted = st.form_submit_button("Apply")

try:
    df = _load_fusions(q, limit)
except Exception as e:
    st.error(f"Query error: {type(e).__name__}: {e}")
    st.stop()

st.caption(f"{len(df)} rows")

df_view = df.copy()
df_view.insert(0, "✓ Select", False)

st.data_editor(
    df_view,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select","fusion_name","fluor","tag","tag_pos","n_plasmids","n_rnas"
    ],
    column_config={
        "✓ Select":   st.column_config.CheckboxColumn("✓ Select", default=False),
        "fusion_name":st.column_config.TextColumn("fusion", disabled=True),
        "fluor":      st.column_config.TextColumn("fluor", disabled=True),
        "tag":        st.column_config.TextColumn("tag", disabled=True),
        "tag_pos":    st.column_config.TextColumn("pos", disabled=True),
        "n_plasmids": st.column_config.NumberColumn("plasmids", disabled=True, format="%d"),
        "n_rnas":     st.column_config.NumberColumn("rnas", disabled=True, format="%d"),
    },
    key="fusions_overview_v1"
)