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
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🧬 Fusions Overview", page_icon="🧬", layout="wide")
st.title("🧬 Fusions Overview")

# ── Engine (cached) ──────────────────────────────────────────────────────────
_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        if not os.getenv("DB_URL"):
            st.error("DB_URL not set"); st.stop()
        _ENGINE = get_engine()
    return _ENGINE

# ── Data loaders ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_fusion_catalog() -> pd.DataFrame:
    sql = """
    with base as (
      select
        f.fusion_code,
        f.fusion_name,
        fl.fluor_name,
        t.tag_name
      from public.fusions f
      left join public.fluors fl on fl.fluor_code = f.fluor_code
      left join public.tags   t  on t.tag_code   = f.tag_code
    ),
    counts as (
      select fusion_code, count(*)::int as n_plasmids
      from public.join_plasmid_fusions
      group by fusion_code
    )
    select
      b.fusion_code,
      b.fusion_name,
      b.fluor_name,
      b.tag_name,
      coalesce(c.n_plasmids, 0) as n_plasmids
    from base b
    left join counts c using (fusion_code)
    order by b.fusion_name
    """
    with _eng().begin() as cx:
        return pd.read_sql(text(sql), cx)

@st.cache_data(ttl=60)
def load_plasmids_for_fusions(fusion_codes: List[str]) -> pd.DataFrame:
    if not fusion_codes:
        return pd.DataFrame(columns=[
            "plasmid_code","plasmid_name","nickname","resistance",
            "supports_invitro_rna","fluor_names","tag_names","fusion_names","notes"
        ])
    sql = """
    select
      r.plasmid_code,
      r.plasmid_name,
      r.nickname,
      r.resistance,
      r.supports_invitro_rna,
      r.fluor_names,
      r.tag_names,
      r.fusion_names,
      r.notes
    from public.v_plasmids_rich r
    where exists (
      select 1
      from public.join_plasmid_fusions pf
      where pf.plasmid_code = r.plasmid_code
        and pf.fusion_code = any(:codes)
    )
    order by r.plasmid_code
    """
    with _eng().begin() as cx:
        return pd.read_sql(text(sql), cx, params={"codes": fusion_codes})

# ── Filters (search + fluor/tag pickers) ─────────────────────────────────────
with _eng().begin() as cx:
    flu_cat = pd.read_sql(text("select fluor_name from public.fluors order by fluor_name"), cx)["fluor_name"].dropna().tolist()
    tag_cat = pd.read_sql(text("select tag_name   from public.tags   order by tag_name"),   cx)["tag_name"].dropna().tolist()

with st.form("filters"):
    c1, c2, c3, c4 = st.columns([2,2,2,1])
    with c1:
        q = st.text_input("Search fusions (supports field filters: fusion:, fluor:, tag:)", "")
    with c2:
        fl_sel = st.multiselect("Filter by fluor(s)", flu_cat)
    with c3:
        tag_sel = st.multiselect("Filter by tag(s)", tag_cat)
    with c4:
        limit = int(st.number_input("Limit", min_value=1, max_value=10000, value=1000, step=200))
    submitted = st.form_submit_button("Apply")

fusions = load_fusion_catalog()

# Apply text/field filters client-side (fast, consistent with other overview pages)
def _tokens(qs: str) -> List[str]:
    return [t for t in shlex.split(qs or "") if t and t.upper() != "AND"]

def _match_row(row: pd.Series) -> bool:
    toks = _tokens(q)
    for tok in toks:
        neg = tok.startswith("-")
        core = tok[1:] if neg else tok
        if ":" in core:
            k, v = core.split(":", 1)
            k = (k or "").strip().lower()
            v = (v or "").strip().lower().strip('"')
            field_val = {
                "fusion": str(row.get("fusion_name", "")),
                "fluor":  str(row.get("fluor_name", "")),
                "tag":    str(row.get("tag_name", "")),
            }.get(
                k,
                f"{row.get('fusion_name','')} {row.get('fluor_name','')} {row.get('tag_name','')}",
            )
            hit = v in field_val.lower()
        else:
            blob = f"{row.get('fusion_name','')} {row.get('fluor_name','')} {row.get('tag_name','')}"
            hit = core.lower() in blob.lower()
        if neg and hit:
            return False
        if not neg and not hit:
            return False
    if fl_sel and (row.get("fluor_name") not in fl_sel):
        return False
    if tag_sel and (row.get("tag_name") not in tag_sel):
        return False
    return True

if q or fl_sel or tag_sel:
    mask = fusions.apply(_match_row, axis=1)
    fusions_view = fusions.loc[mask].copy()
else:
    fusions_view = fusions.copy()

fusions_view = fusions_view.head(limit).reset_index(drop=True)
st.caption(f"Fusions: showing {len(fusions_view):,} of {len(fusions):,}")

# ── Selectable table ─────────────────────────────────────────────────────────
view_cols = ["✓ Select","fusion_name","fluor_name","tag_name","n_plasmids"]
tbl = fusions_view.copy()
tbl.insert(0, "✓ Select", False)

sig = "|".join(tbl.get("fusion_code", pd.Series([], dtype=str)).astype(str).tolist())
if st.session_state.get("_fusions_sig") != sig:
    st.session_state["_fusions_sig"] = sig
    st.session_state["_fusions_table"] = tbl.copy()

edited = st.data_editor(
    st.session_state["_fusions_table"],
    width="stretch",
    hide_index=True,
    column_order=view_cols,
    column_config={
        "✓ Select":   st.column_config.CheckboxColumn("✓ Select", default=False),
        "fusion_name":st.column_config.TextColumn("fusion", disabled=True),
        "fluor_name": st.column_config.TextColumn("fluor",  disabled=True),
        "tag_name":   st.column_config.TextColumn("tag",    disabled=True),
        "n_plasmids": st.column_config.NumberColumn("# plasmids", disabled=True),
    },
    key="fusions_editor",
)
st.session_state["_fusions_table"] = edited.copy()

sel_codes_actual: List[str] = []
if isinstance(edited, pd.DataFrame) and "✓ Select" in edited.columns:
    sel_codes_actual = fusions_view.loc[edited.index[edited["✓ Select"]], "fusion_code"].astype(str).tolist()

cA, cB, cC = st.columns([1,2,2])
with cA:
    st.caption(f"Selected fusions: {len(sel_codes_actual)}")

# ── Drilldown: plasmids containing the selected fusion(s) ────────────────────
if sel_codes_actual:
    st.subheader("Plasmids containing selected fusion(s)")
    plasmids = load_plasmids_for_fusions(sel_codes_actual).copy()
    st.dataframe(
        plasmids[[
            "plasmid_code","plasmid_name","nickname","resistance","supports_invitro_rna",
            "fluor_names","tag_names","fusion_names","notes"
        ]],
        use_container_width=True
    )
else:
    st.info("Select one or more fusions to see the plasmids that contain them.")