# carp_app/ui/pages/110_🔎_overview_fusions.py
from __future__ import annotations
import sys, pathlib, os, shlex
from typing import Optional, List, Dict

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🧬 Fusions Overview", page_icon="🧬", layout="wide")
st.title("🧬 Fusions Overview")

_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        if not os.getenv("DB_URL"):
            st.error("DB_URL not set"); st.stop()
        _ENGINE = get_engine()
    return _ENGINE

@st.cache_data(ttl=60)
def load_ref() -> Dict[str, pd.DataFrame]:
    with _eng().begin() as cx:
        flu = pd.read_sql(text("SELECT id::text AS id, fluor_code, fluor_name FROM public.fluors ORDER BY fluor_code"), cx)
        tag = pd.read_sql(text("SELECT id::text AS id, tag_code, tag_name FROM public.tags ORDER BY tag_code"), cx)
    return {"flu": flu, "tag": tag}

@st.cache_data(ttl=60)
def load_fusion_catalog() -> pd.DataFrame:
    sql = """
    WITH base AS (
      SELECT
        f.id::text      AS fusion_id,
        f.fusion_code,
        f.fusion_name,
        fl.fluor_name,
        fl.fluor_code,
        tg.tag_name,
        tg.tag_code
      FROM public.fusions f
      LEFT JOIN public.fluors  fl ON fl.id = f.fluor_id
      LEFT JOIN public.tags    tg ON tg.id = f.tag_id
    ),
    counts AS (
      SELECT jpf.fusion_id::text AS fusion_id, COUNT(*)::int AS n_plasmids
      FROM public.join_plasmid_fusions jpf
      GROUP BY jpf.fusion_id
    )
    SELECT
      b.fusion_id,
      b.fusion_code,
      b.fusion_name,
      b.fluor_name,
      b.fluor_code,
      b.tag_name,
      b.tag_code,
      COALESCE(c.n_plasmids, 0) AS n_plasmids
    FROM base b
    LEFT JOIN counts c USING (fusion_id)
    ORDER BY b.fusion_name NULLS LAST, b.fusion_code
    """
    with _eng().begin() as cx:
        return pd.read_sql(text(sql), cx)

@st.cache_data(ttl=60)
def load_plasmids_for_fusions(fusion_ids: List[str]) -> pd.DataFrame:
    if not fusion_ids:
        return pd.DataFrame(columns=["code","name","nickname","resistance","fluors","tags","fusions","notes"])
    sql = """
    SELECT
      vp.code, vp.name, vp.nickname, vp.resistance,
      vp.fluors, vp.tags, vp.fusions, vp.notes
    FROM public.v_plasmids AS vp
    WHERE vp.id IN (
      SELECT DISTINCT jpf.plasmid_id
      FROM public.join_plasmid_fusions AS jpf
      WHERE jpf.fusion_id = ANY(:ids)
    )
    ORDER BY vp.code
    """
    with _eng().begin() as cx:
        return pd.read_sql(text(sql), cx, params={"ids": fusion_ids})

ref = load_ref()
flu_codes = ref["flu"]["fluor_code"].dropna().astype(str).tolist()
tag_codes = ref["tag"]["tag_code"].dropna().astype(str).tolist()
flu_code_to_id = dict(ref["flu"][["fluor_code","id"]].values)
tag_code_to_id = dict(ref["tag"][["tag_code","id"]].values)

with st.form("filters"):
    c1, c2, c3, c4 = st.columns([2,2,2,1])
    with c1:
        q = st.text_input("Search fusions (supports filters: fusion:, fluor:, tag:)", "")
    with c2:
        fl_sel = st.multiselect("Filter by fluor code(s)", flu_codes)
    with c3:
        tag_sel = st.multiselect("Filter by tag code(s)", tag_codes)
    with c4:
        limit = int(st.number_input("Limit", min_value=1, max_value=10000, value=1000, step=200))
    submitted = st.form_submit_button("Apply")

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
                "fusion": f"{row.get('fusion_name','')} {row.get('fusion_code','')}",
                "fluor":  f"{row.get('fluor_name','')} {row.get('fluor_code','')}",
                "tag":    f"{row.get('tag_name','')} {row.get('tag_code','')}",
            }.get(k, f"{row.get('fusion_name','')} {row.get('fluor_name','')} {row.get('tag_name','')}")
            hit = v in field_val.lower()
        else:
            blob = f"{row.get('fusion_name','')} {row.get('fluor_name','')} {row.get('tag_name','')}"
            hit = core.lower() in blob.lower()
        if neg and hit: return False
        if not neg and not hit: return False
    if fl_sel and (row.get("fluor_code") not in fl_sel): return False
    if tag_sel and (row.get("tag_code") not in tag_sel): return False
    return True

fusions = load_fusion_catalog()
fusions_view = fusions.loc[fusions.apply(_match_row, axis=1)].copy() if (q or fl_sel or tag_sel) else fusions.copy()
fusions_view = fusions_view.head(limit).reset_index(drop=True)
st.caption(f"Fusions: showing {len(fusions_view):,} of {len(fusions):,}")

# ===== READ-ONLY MASTER TABLE =================================================
view_cols = ["✓ Select","fusion_code","fusion_name","fluor_code","tag_code","n_plasmids"]
tbl = fusions_view.copy()
tbl.insert(0, "✓ Select", False)

sig = "|".join(tbl.get("fusion_id", pd.Series([], dtype=str)).astype(str).tolist())
if st.session_state.get("_fusions_sig") != sig:
    st.session_state["_fusions_sig"] = sig
    st.session_state["_fusions_table"] = tbl.copy()
    st.session_state["_fusions_original"] = tbl.copy()

ro = st.data_editor(
    st.session_state["_fusions_table"],
    use_container_width=True,
    hide_index=True,
    height=520,
    num_rows="fixed",
    column_order=view_cols,
    column_config={
        "✓ Select":    st.column_config.CheckboxColumn("✓ Select", default=False),
        "fusion_code": st.column_config.TextColumn("fusion_code", disabled=True),
        "fusion_name": st.column_config.TextColumn("fusion_name", disabled=True),
        "fluor_code":  st.column_config.TextColumn("fluor_code", disabled=True),
        "tag_code":    st.column_config.TextColumn("tag_code", disabled=True),
        "n_plasmids":  st.column_config.NumberColumn("# plasmids", disabled=True),
    },
    key="fusions_ro",
)
st.session_state["_fusions_table"]["✓ Select"] = ro["✓ Select"].values

st.divider()

# ===== EDIT SELECTION PANEL ===================================================
st.subheader("Edit selection")

edit_options = ["fusion_name", "fluor_code", "tag_code"]
cL, cR = st.columns([2,2])
with cL:
    editable_cols = st.multiselect(
        "1) Choose which columns are editable",
        options=edit_options,
        help="Only these columns will be editable below."
    )
with cR:
    sel_mask = st.session_state["_fusions_table"]["✓ Select"] == True
    sel_ids = fusions_view.loc[sel_mask, "fusion_id"].astype(str).tolist() if sel_mask.any() else []
    st.metric("Selected rows", len(sel_ids))

if not sel_ids or not editable_cols:
    st.info("Select at least one row in the table above and choose one or more editable columns.")
else:
    base_all = st.session_state["_fusions_table"].copy()
    edit_slice = base_all.loc[sel_mask, ["fusion_id","fusion_code"] + editable_cols].reset_index(drop=True)

    col_cfg = {
        "fusion_code": st.column_config.TextColumn("fusion_code", disabled=True),
        "fusion_name": st.column_config.TextColumn("fusion_name", disabled=("fusion_name" not in editable_cols)),
        "fluor_code":  st.column_config.SelectboxColumn("fluor_code", options=flu_codes, disabled=("fluor_code" not in editable_cols)),
        "tag_code":    st.column_config.SelectboxColumn("tag_code", options=tag_codes, disabled=("tag_code" not in editable_cols)),
    }

    st.caption("Edit the selected rows/columns below, then save.")
    edited_slice = st.data_editor(
        edit_slice,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="fusions_edit_slice",
        column_config=col_cfg,
    )

    do_save = st.button("💾 Save selected edits", type="primary")

    if do_save:
        orig_all = st.session_state["_fusions_original"].set_index("fusion_code")
        cur_rows = edited_slice.set_index("fusion_code")
        to_update: List[Dict] = []

        for code, row in cur_rows.iterrows():
            changed = {}
            for col in editable_cols:
                old = orig_all.at[code, col] if (code in orig_all.index and col in orig_all.columns) else None
                new = row.get(col)
                if (pd.isna(old) and pd.isna(new)) or (old == new):
                    continue
                changed[col] = None if pd.isna(new) else new
            if changed:
                changed["fusion_id"] = fusions_view.loc[fusions_view["fusion_code"] == code, "fusion_id"].iloc[0]
                to_update.append(changed)

        if not to_update:
            st.success("No changes detected.")
        else:
            with _eng().begin() as cx:
                for rec in to_update:
                    sets = []
                    params = {"fid": rec["fusion_id"]}
                    if "fusion_name" in rec:
                        sets.append("fusion_name = :fname")
                        params["fname"] = rec["fusion_name"]
                    if "fluor_code" in rec:
                        sets.append("fluor_id = :flid")
                        params["flid"] = flu_code_to_id.get(rec["fluor_code"])
                    if "tag_code" in rec:
                        sets.append("tag_id = :tgid")
                        params["tgid"] = tag_code_to_id.get(rec["tag_code"])
                    if not sets:
                        continue
                    sql = text(f"UPDATE public.fusions SET {', '.join(sets)} WHERE id = :fid")
                    cx.execute(sql, params)

            # reflect changes into session tables and original baseline
            for rec in to_update:
                code = fusions_view.loc[fusions_view["fusion_id"] == rec["fusion_id"], "fusion_code"].iloc[0]
                for k, v in rec.items():
                    if k == "fusion_id": continue
                    st.session_state["_fusions_table"].loc[
                        st.session_state["_fusions_table"]["fusion_code"] == code, k
                    ] = v
                    st.session_state["_fusions_original"].loc[
                        st.session_state["_fusions_original"]["fusion_code"] == code, k
                    ] = v
            st.success(f"Saved {len(to_update)} updated row(s).")

st.divider()

# ===== ADD NEW FUSION (guarded form) =========================================
with st.expander("➕ Add new fusion"):
    with st.form("add_fusion"):
        new_code = st.text_input("fusion_code (required)", "")
        new_name = st.text_input("fusion_name (required)", "")
        new_flu  = st.selectbox("fluor_code", options=[""] + flu_codes, index=0)
        new_tag  = st.selectbox("tag_code",   options=[""] + tag_codes, index=0)
        submitted_add = st.form_submit_button("Insert")

    if submitted_add:
        code_ok = (new_code or "").strip()
        name_ok = (new_name or "").strip()
        if not code_ok or not name_ok:
            st.error("Both fusion_code and fusion_name are required.")
        else:
            with _eng().begin() as cx:
                sql = text("""
                    INSERT INTO public.fusions(fusion_code, fusion_name, fluor_id, tag_id)
                    VALUES (:code, :name, :flid, :tgid)
                    ON CONFLICT (fusion_code) DO NOTHING
                """)
                cx.execute(sql, {
                    "code": code_ok,
                    "name": name_ok,
                    "flid": flu_code_to_id.get(new_flu) if new_flu else None,
                    "tgid": tag_code_to_id.get(new_tag) if new_tag else None,
                })
            new_row = {
                "✓ Select": False,
                "fusion_id": "",  # not reloaded; will populate on next refresh
                "fusion_code": code_ok,
                "fusion_name": name_ok,
                "fluor_code": new_flu or None,
                "tag_code": new_tag or None,
                "n_plasmids": 0,
            }
            st.session_state["_fusions_table"] = pd.concat(
                [st.session_state["_fusions_table"], pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.session_state["_fusions_original"] = pd.concat(
                [st.session_state["_fusions_original"], pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success(f"Inserted fusion {code_ok}.")

# ===== DRILLDOWN: plasmids for selection =====================================
sel_ids_actual: List[str] = []
if "✓ Select" in st.session_state["_fusions_table"].columns:
    sel_ids_actual = fusions_view.loc[
        st.session_state["_fusions_table"].index[st.session_state["_fusions_table"]["✓ Select"]],
        "fusion_id"
    ].astype(str).tolist() if len(fusions_view) else []

if sel_ids_actual:
    st.subheader("Plasmids containing selected fusion(s)")
    plasmids = load_plasmids_for_fusions(sel_ids_actual)
    if plasmids.empty:
        st.info("No plasmids found for the selected fusion(s).")
    else:
        st.dataframe(plasmids[["code","name","nickname","resistance","fluors","tags","fusions","notes"]], use_container_width=True)
else:
    st.info("Select one or more fusions to see the plasmids that contain them.")