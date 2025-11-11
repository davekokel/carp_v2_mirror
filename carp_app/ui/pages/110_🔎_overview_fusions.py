# carp_app/ui/pages/110_🧬_overview_fusions.py
from __future__ import annotations
import os, sys, pathlib, shlex
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── repo path/bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

from carp_app.ui.lib.app_ctx import get_engine as _create_engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Fusions Overview", page_icon="🧬", layout="wide")
st.title("🧬 Fusions Overview")

# ───────── engine cache ─────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _eng() -> Engine:
    return _cached_engine()

# ───────── helpers ─────────
def _load_refdata() -> tuple[List[str], List[str], List[str]]:
    with _eng().begin() as cx:
        fluors = [r["fluor_code"] for r in cx.execute(text(
            "select fluor_code from public.fluors order by 1"
        )).mappings().all()]
        tags = [r["tag_code"] for r in cx.execute(text(
            "select tag_code from public.tags order by 1"
        )).mappings().all()]
    tag_positions = ["", "N", "C", "N-term", "C-term", "internal"]
    return fluors, tags, tag_positions

def _build_query(q: str, limit: int) -> tuple[str, dict]:
    import shlex
    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    params: dict = {"lim": int(limit)}
    where: list[str] = []

    # columns available on v_fusions_overview
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
        id, fusion_name, fluor, tag, tag_pos, n_plasmids, n_rnas, created_at
      FROM public.v_fusions_overview
      {where_sql}
      ORDER BY n_plasmids DESC, n_rnas DESC, {c_fluor}, {c_tag} NULLS FIRST, {c_pos} NULLS FIRST
      LIMIT :lim
    """
    return sql, params

def _load_fusions(q: str, limit: int) -> pd.DataFrame:
    sql, params = _build_query(q, limit)
    with _eng().begin() as cx:
        df = pd.read_sql(text(sql), cx, params=params)
    for c in df.select_dtypes(include=["object","string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _update_fusions(ids: List[str], name: Optional[str], tag_pos: Optional[str]) -> int:
    if not ids:
        return 0
    count = 0
    with _eng().begin() as cx:
        for fid in ids:
            sets = []
            vals = {"id": fid}
            if name is not None:
                sets.append("name = :name")
                vals["name"] = name if name.strip() else None
            if tag_pos is not None:
                sets.append("tag_pos = NULLIF(:pos,'')")
                vals["pos"] = tag_pos
            if sets:
                cx.execute(text(f"UPDATE public.fusions SET {', '.join(sets)} WHERE id = :id"), vals)
                count += 1
    return count

def _ensure_fusion(fluor_code: Optional[str], tag_code: Optional[str],
                   tag_pos: Optional[str], fusion_name: Optional[str]) -> str:
    if not fluor_code and not tag_code:
        raise ValueError("at least one of fluor_code or tag_code is required")
    with _eng().begin() as cx:
        fid = cx.execute(text("SELECT id FROM public.fluors WHERE fluor_code=:c LIMIT 1"),
                         {"c": fluor_code}).scalar() if fluor_code else None
        tid = cx.execute(text("SELECT id FROM public.tags WHERE tag_code=:c LIMIT 1"),
                         {"c": tag_code}).scalar() if tag_code else None
        if fluor_code and not fid:
            raise ValueError(f"unknown fluor_code: {fluor_code}")
        if tag_code and not tid:
            raise ValueError(f"unknown tag_code: {tag_code}")

        fusion_id = cx.execute(text("""
            WITH ins AS (
              INSERT INTO public.fusions (fluor_id, tag_id, tag_pos, name)
              VALUES (:fid, :tid, NULLIF(:pos,''), NULLIF(:fname,''))
              ON CONFLICT DO NOTHING
              RETURNING id
            )
            SELECT id FROM ins
            UNION ALL
            SELECT id FROM public.fusions
             WHERE (fluor_id IS NOT DISTINCT FROM :fid)
               AND (tag_id  IS NOT DISTINCT FROM :tid)
               AND COALESCE(tag_pos,'') = COALESCE(:pos,'')
            LIMIT 1
        """), {"fid": fid, "tid": tid, "pos": (tag_pos or ""), "fname": (fusion_name or None)}).scalar()
        if not fusion_id:
            raise RuntimeError("unable to create or locate fusion")
        return str(fusion_id)

# ───────── Filters ─────────
with st.form("filters", clear_on_submit=False):
    c1, c2 = st.columns([3,1])
    with c1:
        q = st.text_input("Search (supports fluor:, tag:, pos:, name:)", "")
    with c2:
        limit = int(st.number_input("Limit", min_value=10, max_value=20000, value=2000, step=500))
    _ = st.form_submit_button("Apply")

# ───────── Data table ─────────
try:
    df = _load_fusions(q, limit)
except Exception as e:
    st.error(f"Query error: {type(e).__name__}: {e}")
    st.stop()

st.caption(f"{len(df)} rows")

view = df.copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_order=["✓ Select","fusion_name","fluor","tag","tag_pos","n_plasmids","n_rnas"],
    column_config={
        "✓ Select":    st.column_config.CheckboxColumn("✓ Select", default=False),
        "fusion_name": st.column_config.TextColumn("fusion", disabled=True),
        "fluor":       st.column_config.TextColumn("fluor", disabled=True),
        "tag":         st.column_config.TextColumn("tag", disabled=True),
        "tag_pos":     st.column_config.TextColumn("pos", disabled=True),
        "n_plasmids":  st.column_config.NumberColumn("plasmids", disabled=True, format="%d"),
        "n_rnas":      st.column_config.NumberColumn("rnas", disabled=True, format="%d"),
    },
    key="fusions_overview_v2",
)

# ───────── Plasmids containing the selected fusion (single-select preview) ─────────
selected_ids = []
selected_map = {}  # fusion_id -> fusion_name (for display)

if isinstance(grid, pd.DataFrame) and "✓ Select" in grid.columns:
    sel = grid.loc[grid["✓ Select"] == True]
    if not sel.empty and "id" in sel.columns:
        selected_ids = sel["id"].astype(str).tolist()
        if "fusion_name" in sel.columns:
            selected_map = dict(zip(sel["id"].astype(str), sel["fusion_name"].astype(str)))

if len(selected_ids) == 1:
    fusion_id = selected_ids[0]
    fusion_name = selected_map.get(fusion_id, fusion_id)

    with _eng().begin() as cx:
        plasmids_df = pd.read_sql(
            text("""
                SELECT
                  p.code,
                  COALESCE(p.name,'')      AS name,
                  COALESCE(p.nickname,'')  AS nickname,
                  COALESCE(p.resistance,'') AS resistance,
                  p.created_at
                FROM public.join_plasmid_fusions jpf
                JOIN public.plasmids p ON p.id = jpf.plasmid_id
                WHERE jpf.fusion_id = :fid
                ORDER BY p.created_at DESC NULLS LAST, p.code
            """),
            cx,
            params={"fid": fusion_id},
        )

    st.subheader(f"Plasmids containing: {fusion_name}")
    if plasmids_df.empty:
        st.info("No plasmids are currently linked to this fusion.")
    else:
        st.dataframe(
            plasmids_df[["code","name","nickname","resistance","created_at"]],
            width="stretch",
            hide_index=True
        )
        st.download_button(
            "⬇︎ Download plasmids (CSV)",
            data=plasmids_df.to_csv(index=False).encode("utf-8"),
            file_name=f"plasmids_for_fusion_{fusion_name}_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
            type="secondary",
            width="stretch",
        )
elif len(selected_ids) > 1:
    st.info("Select exactly one fusion to preview its plasmids here.")
else:
    st.caption("Tip: check a fusion row above to preview its plasmids.")

st.divider()
# ───────── Edit selection ─────────
st.subheader("Edit selection")
selected_ids = []
if isinstance(grid, pd.DataFrame) and "✓ Select" in grid.columns:
    sel = grid.loc[grid["✓ Select"] == True]
    if not sel.empty and "id" in sel.columns:
        selected_ids = sel["id"].astype(str).tolist()

c1, c2, c3 = st.columns([2,2,1])
with c1:
    new_name = st.text_input("Set fusion name (applies to selected; leave blank to clear)", "")
with c2:
    _, _, tag_positions = _load_refdata()
    new_pos = st.selectbox("Set tag position (applies to selected)", tag_positions, index=0)
with c3:
    applied = st.button("Apply changes", type="primary", disabled=(len(selected_ids) == 0))

if applied:
    try:
        changed = _update_fusions(
            selected_ids,
            name=(new_name if new_name != "" else ""),
            tag_pos=new_pos if new_pos is not None else ""
        )
        st.success(f"Updated {changed} fusion(s). Reload the table to see changes.")
    except Exception as e:
        st.error(f"Update failed: {e}")

st.divider()

# ───────── Add new fusion(s) ─────────
st.subheader("Add new fusion(s)")
fluors, tags, tag_positions = _load_refdata()
if "new_fusions_df" not in st.session_state:
    st.session_state.new_fusions_df = pd.DataFrame(
        [{"fluor_code":"", "tag_code":"", "tag_pos":"", "name":""}]
    )

add_df = st.data_editor(
    st.session_state.new_fusions_df,
    num_rows="dynamic",
    width="stretch",
    hide_index=True,
    column_config={
        "fluor_code": st.column_config.SelectboxColumn("fluor_code", options=fluors, required=False),
        "tag_code":   st.column_config.SelectboxColumn("tag_code",   options=tags,   required=False),
        "tag_pos":    st.column_config.SelectboxColumn("tag_pos",    options=tag_positions, required=False),
        "name":       st.column_config.TextColumn("name (optional)"),
    },
    key="new_fusions_editor",
)

if st.button("Insert fusion rows", type="primary"):
    rows = []
    for _, r in add_df.fillna("").iterrows():
        f = (r.get("fluor_code") or "").strip() or None
        t = (r.get("tag_code") or "").strip() or None
        p = (r.get("tag_pos") or "").strip()
        n = (r.get("name") or "").strip() or None
        if not f and not t:
            continue
        try:
            _ensure_fusion(f, t, p, n)
            rows.append((f, t, p, n))
        except Exception as e:
            st.error(f"Row skipped [{f},{t},{p},{n}]: {e}")
    st.success(f"Inserted/ensured {len(rows)} fusion(s).")
    # reset editor to a single blank row
    st.session_state.new_fusions_df = pd.DataFrame(
        [{"fluor_code":"", "tag_code":"", "tag_pos":"", "name":""}]
    )