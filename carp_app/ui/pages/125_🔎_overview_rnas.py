# carp_app/ui/pages/125_🔎_overview_rnas.py
from __future__ import annotations

import os, sys, pathlib
from typing import Optional, List, Dict

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo wiring
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine as _engine

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🔎 Overview RNAs", page_icon="🧬", layout="wide")
st.title("🔎 Overview RNAs")

@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _engine()

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2 = st.columns([3,1])
    with c1:
        q = st.text_input("Search (code/name/base/markers/notes)", "")
    with c2:
        limit = int(st.number_input("Limit", min_value=50, max_value=5000, value=500, step=50))
    st.form_submit_button("Apply", use_container_width=True)

# Pull whatever the view exposes; normalize columns in Python
sql = text("""
  SELECT * FROM public.v_rnas
  ORDER BY created_at DESC NULLS LAST, rna_code
  LIMIT :lim
""")
with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params={"lim": int(limit)})

# Apply text filter client-side (no guessing DB columns)
def _contains(s: pd.Series, needle: str) -> pd.Series:
    return s.fillna("").astype(str).str.contains(needle, case=False, na=False)

if q.strip():
    needle = q.strip()
    cols_for_filter = [c for c in df.columns if df[c].dtype == object or str(df[c].dtype).startswith(("string","object"))]
    if cols_for_filter:
        mask = pd.Series(False, index=df.index)
        for c in cols_for_filter:
            mask |= _contains(df[c], needle)
        df = df.loc[mask].copy()

# Ensure friendly columns exist even if the view doesn’t have them
must_have = [
    "rna_code",
    "rna_name",
    "base_plasmid_code",   # code only
    "fusion_names",        # optional: list of fusion names
    "fluor_names",
    "tag_names",
    "notes",
    "created_by",
    "created_at",
]
for c in must_have:
    if c not in df.columns:
        df[c] = "" if c != "created_at" else pd.NaT

# Reorder for display
display_cols = [c for c in must_have if c in df.columns]
extras = [c for c in df.columns if c not in display_cols]
df = df[display_cols + extras]

st.caption(f"{len(df)} row(s)")

# ===== READ-ONLY MASTER TABLE ================================================
view_cols = [
    "✓ Select",
    "rna_code","rna_name","base_plasmid_code",
    "fusion_names","fluor_names","tag_names",
    "notes","created_by","created_at"
]

tbl = df.copy()
tbl.insert(0, "✓ Select", False)

# keep originals and a stable signature
sig = "|".join(tbl.get("rna_code", pd.Series([], dtype=str)).astype(str).tolist())
if st.session_state.get("_rnas_sig") != sig:
    st.session_state["_rnas_sig"] = sig
    st.session_state["_rnas_table"] = tbl.copy()
    st.session_state["_rnas_original"] = tbl.copy()

ro = st.data_editor(
    st.session_state["_rnas_table"],
    use_container_width=True,
    hide_index=True,
    height=520,
    num_rows="fixed",  # lock master grid: no inline edits here
    column_order=view_cols,
    column_config={
        "✓ Select":          st.column_config.CheckboxColumn("✓ Select", default=False),
        "rna_code":          st.column_config.TextColumn("RNA code", disabled=True),
        "rna_name":          st.column_config.TextColumn("RNA name", disabled=True),
        "base_plasmid_code": st.column_config.TextColumn("Base plasmid code", disabled=True),
        "fusion_names":      st.column_config.TextColumn("Fusion names", disabled=True),
        "fluor_names":       st.column_config.TextColumn("Fluor names", disabled=True),
        "tag_names":         st.column_config.TextColumn("Tag names", disabled=True),
        "notes":             st.column_config.TextColumn("Notes", disabled=True),
        "created_by":        st.column_config.TextColumn("Created by", disabled=True),
        "created_at":        st.column_config.DatetimeColumn("Created at", disabled=True),
    },
    key="rnas_ro",
)
st.session_state["_rnas_table"]["✓ Select"] = ro["✓ Select"].values

st.divider()

# ===== EDIT SELECTION PANEL ===================================================
st.subheader("Edit selection")

EDITABLE_COLS = ["rna_name", "base_plasmid_code", "notes"]

cL, cR = st.columns([2,2])
with cL:
    editable_cols = st.multiselect(
        "1) Choose which columns are editable",
        options=EDITABLE_COLS,
        help="Only these columns will be editable below."
    )
with cR:
    sel_mask = st.session_state["_rnas_table"]["✓ Select"] == True
    sel_codes = st.session_state["_rnas_table"].loc[sel_mask, "rna_code"].dropna().astype(str).tolist()
    st.metric("Selected rows", len(sel_codes))

if not sel_codes or not editable_cols:
    st.info("Select at least one row in the table above and choose one or more editable columns.")
else:
    base_all = st.session_state["_rnas_table"].set_index("rna_code")
    edit_slice = base_all.loc[sel_codes].reset_index()

    col_cfg = {
        "rna_code":          st.column_config.TextColumn("RNA code", disabled=True),
        "rna_name":          st.column_config.TextColumn("RNA name", disabled=("rna_name" not in editable_cols)),
        "base_plasmid_code": st.column_config.TextColumn("Base plasmid code", disabled=("base_plasmid_code" not in editable_cols)),
        "notes":             st.column_config.TextColumn("Notes", disabled=("notes" not in editable_cols)),
    }

    st.caption("Edit the selected rows/columns below, then save.")
    edited_slice = st.data_editor(
        edit_slice[["rna_code"] + sorted(set(editable_cols))],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="rnas_edit_slice",
        column_config=col_cfg,
    )

    do_save = st.button("💾 Save selected edits", type="primary")

    if do_save:
        orig_all = st.session_state["_rnas_original"].set_index("rna_code")
        cur_rows = edited_slice.set_index("rna_code")
        to_update: List[Dict] = []

        for code, row in cur_rows.iterrows():
            changed: Dict[str, object] = {}
            for col in editable_cols:
                old = orig_all.at[code, col] if (code in orig_all.index and col in orig_all.columns) else None
                new = row.get(col)
                if (pd.isna(old) and pd.isna(new)) or (old == new):
                    continue
                changed[col] = None if pd.isna(new) else new
            if changed:
                changed["rna_code"] = code
                to_update.append(changed)

        if not to_update:
            st.success("No changes detected.")
        else:
            upd_sql = text("""
                UPDATE public.rnas
                   SET rna_name = COALESCE(:rna_name, rna_name),
                       base_plasmid_code = COALESCE(:base_plasmid_code, base_plasmid_code),
                       notes = COALESCE(:notes, notes)
                 WHERE rna_code = :rna_code
            """)

            n_upd = 0
            with _eng().begin() as cx:
                for rec in to_update:
                    payload = {
                        "rna_code": rec["rna_code"],
                        "rna_name": rec.get("rna_name"),
                        "base_plasmid_code": rec.get("base_plasmid_code"),
                        "notes": rec.get("notes"),
                    }
                    cx.execute(upd_sql, payload)
                    n_upd += 1

            # reflect into session tables and baseline
            for rec in to_update:
                code = rec["rna_code"]
                for k, v in rec.items():
                    if k == "rna_code": continue
                    st.session_state["_rnas_table"].loc[
                        st.session_state["_rnas_table"]["rna_code"] == code, k
                    ] = v
                    st.session_state["_rnas_original"].loc[
                        st.session_state["_rnas_original"]["rna_code"] == code, k
                    ] = v

            st.success(f"Saved {n_upd} updated row(s).")

st.divider()

# ===== ADD NEW RNA (guarded form) ============================================
with st.expander("➕ Add new RNA"):
    with st.form("add_rna"):
        new_code = st.text_input("rna_code (required)", "")
        new_name = st.text_input("rna_name (required)", "")
        new_base = st.text_input("base_plasmid_code", "")
        new_notes = st.text_area("notes", "")
        submitted_add = st.form_submit_button("Insert")

    if submitted_add:
        code_ok = (new_code or "").strip()
        name_ok = (new_name or "").strip()
        if not code_ok or not name_ok:
            st.error("Both rna_code and rna_name are required.")
        else:
            ins_sql = text("""
                INSERT INTO public.rnas (rna_code, rna_name, base_plasmid_code, notes, created_by)
                VALUES (:code, :name, :base, :notes, :by)
                ON CONFLICT (rna_code) DO NOTHING
            """)
            by = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
            with _eng().begin() as cx:
                cx.execute(ins_sql, {
                    "code": code_ok,
                    "name": name_ok,
                    "base": (new_base or None),
                    "notes": (new_notes or None),
                    "by": by,
                })

            # add to UI tables; v_rnas-derived fields (fusion/fluor/tag names) left empty
            row = {
                "✓ Select": False,
                "rna_code": code_ok,
                "rna_name": name_ok,
                "base_plasmid_code": (new_base or None),
                "fusion_names": "",
                "fluor_names": "",
                "tag_names": "",
                "notes": (new_notes or None),
                "created_by": by,
                "created_at": pd.Timestamp.utcnow(),
            }
            st.session_state["_rnas_table"] = pd.concat(
                [st.session_state["_rnas_table"], pd.DataFrame([row])],
                ignore_index=True
            )
            st.session_state["_rnas_original"] = pd.concat(
                [st.session_state["_rnas_original"], pd.DataFrame([row])],
                ignore_index=True
            )
            st.success(f"Inserted RNA {code_ok}.")

# ===== Download CSV ===========================================================
st.download_button(
    "⬇︎ Download CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="overview_rnas.csv",
    type="secondary",
    use_container_width=True,
)