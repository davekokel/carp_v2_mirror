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

# ── Introspection (verify only the fields we still use) ──────────────────────
@st.cache_resource(show_spinner=False)
def _rnas_colmap() -> Dict[str, Optional[str]]:
    """
    Map logical fields to actual rnas columns.
    Keys: id, code, notes, by, at
    """
    wanted = {
        "id":   ["id"],
        "code": ["rna_code", "code"],
        "notes":["notes", "note", "description"],
        "by":   ["created_by", "author", "owner"],
        "at":   ["created_at", "inserted_at", "ts", "created"],
    }
    with _eng().begin() as cx:
        cols = [r["column_name"] for r in cx.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='rnas'
        """)).mappings().all()]
    present = {c.lower(): c for c in cols}
    out: Dict[str, Optional[str]] = {}
    for logical, candidates in wanted.items():
        out[logical] = next((present[c] for c in candidates if c in present), None)

    if out["id"] is None:
        st.error("public.rnas must have an id column to join to join_rna_fusions."); st.stop()
    if out["code"] is None:
        st.error("public.rnas must have a code column (rna_code/code)."); st.stop()
    return out

colmap = _rnas_colmap()
HAS = {k: (colmap[k] is not None) for k in colmap.keys()}

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2 = st.columns([3,1])
    with c1:
        q = st.text_input("Search (code/markers/notes)", "")
    with c2:
        limit = int(st.number_input("Limit", min_value=50, max_value=5000, value=500, step=50))
    st.form_submit_button("Apply", use_container_width=True)

# ── Load from base tables (no views) ─────────────────────────────────────────
def _load_rnas(limit: int) -> pd.DataFrame:
    names_parts = [
        f"r.{colmap['id']}   AS id",
        f"r.{colmap['code']} AS rna_code",
        (f"COALESCE(r.{colmap['notes']},'') AS notes") if HAS["notes"] else "''::text AS notes",
        (f"COALESCE(r.{colmap['by']},'')    AS created_by") if HAS["by"] else "''::text AS created_by",
        (f"r.{colmap['at']}                 AS created_at") if HAS["at"] else "NULL::timestamptz AS created_at",
    ]
    names_select = ",\n          ".join(names_parts)

    sql = text(f"""
      WITH names AS (
        SELECT
          {names_select}
        FROM public.rnas r
      ),
      agg AS (
        SELECT
          n.*,
          COALESCE(string_agg(DISTINCT fl.fluor_code, ',' ORDER BY fl.fluor_code), '') AS fluor_names,
          COALESCE(string_agg(DISTINCT tg.tag_code,   ',' ORDER BY tg.tag_code),   '') AS tag_names,
          COALESCE(string_agg(
            DISTINCT NULLIF(concat_ws('::', COALESCE(fl.fluor_code,''), COALESCE(tg.tag_code,'')),''),
            ',' ORDER BY NULLIF(concat_ws('::', COALESCE(fl.fluor_code,''), COALESCE(tg.tag_code,'')),'')
          ), '') AS fusion_names
        FROM names n
        LEFT JOIN public.join_rna_fusions jrf ON jrf.rna_id = n.id
        LEFT JOIN public.fusions f           ON f.id = jrf.fusion_id
        LEFT JOIN public.fluors  fl          ON fl.id = f.fluor_id
        LEFT JOIN public.tags    tg          ON tg.id = f.tag_id
        GROUP BY n.id, n.rna_code, n.notes, n.created_by, n.created_at
      )
      SELECT
        rna_code,
        fusion_names, fluor_names, tag_names,
        notes, created_by, created_at
      FROM agg
      ORDER BY created_at DESC NULLS LAST, rna_code
      LIMIT :lim
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"lim": int(limit)})
    for c in df.select_dtypes(include=["object","string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

df = _load_rnas(limit=int(limit))

# client-side contains
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

st.caption(f"{len(df)} row(s)")

# ===== READ-ONLY MASTER TABLE ================================================
view_cols = [
    "✓ Select",
    "rna_code",
    "fusion_names","fluor_names","tag_names",
    "notes","created_by","created_at",
]
for c in view_cols:
    if c not in df.columns and c != "✓ Select":
        df[c] = "" if c != "created_at" else pd.NaT

tbl = df[[c for c in view_cols if c != "✓ Select"]].copy()
tbl.insert(0, "✓ Select", False)

sig = "|".join(tbl.get("rna_code", pd.Series([], dtype=str)).astype(str).tolist())
if st.session_state.get("_rnas_sig") != sig:
    st.session_state["_rnas_sig"] = sig
    st.session_state["_rnas_table"] = tbl.copy()
    st.session_state["_rnas_original"] = tbl.copy()

ro = st.data_editor(
    st.session_state["_rnas_table"],
    width="stretch",
    hide_index=True,
    height=520,
    num_rows="fixed",
    column_order=view_cols,
    column_config={
        "✓ Select":   st.column_config.CheckboxColumn("✓ Select", default=False),
        "rna_code":   st.column_config.TextColumn("RNA code", disabled=True),
        "fusion_names": st.column_config.TextColumn("Fusion names", disabled=True),
        "fluor_names":  st.column_config.TextColumn("Fluor names", disabled=True),
        "tag_names":    st.column_config.TextColumn("Tag names", disabled=True),
        "notes":        st.column_config.TextColumn("Notes", disabled=not HAS["notes"]),
        "created_by":   st.column_config.TextColumn("Created by", disabled=True),
        "created_at":   st.column_config.DatetimeColumn("Created at", disabled=True),
    },
    key="rnas_ro",
)
st.session_state["_rnas_table"]["✓ Select"] = ro["✓ Select"].values

st.divider()

# ===== EDIT SELECTION PANEL (notes only if present) ==========================
st.subheader("Edit selection")

EDITABLE_COLS = ["notes"] if HAS["notes"] else []

cL, cR = st.columns([2,2])
with cL:
    editable_cols = st.multiselect(
        "1) Choose which columns are editable",
        options=EDITABLE_COLS,
        default=EDITABLE_COLS,
        help="Only columns that exist in public.rnas are available."
    )
with cR:
    sel_mask = st.session_state["_rnas_table"]["✓ Select"] == True
    sel_codes = st.session_state["_rnas_table"].loc[sel_mask, "rna_code"].dropna().astype(str).tolist()
    st.metric("Selected rows", len(sel_codes))

if not sel_codes or not editable_cols:
    st.info("Select at least one row in the table above.")
else:
    base_all = st.session_state["_rnas_table"].set_index("rna_code")
    for c in editable_cols:
        if c not in base_all.columns:
            base_all[c] = ""
            st.session_state["_rnas_original"][c] = ""
    edit_slice = base_all.loc[sel_codes].reset_index()[["rna_code"] + editable_cols]

    col_cfg = {
        "rna_code": st.column_config.TextColumn("RNA code", disabled=True),
        "notes":    st.column_config.TextColumn("Notes", disabled=("notes" not in editable_cols)),
    }

    st.caption("Edit the selected rows/columns below, then save.")
    edited_slice = st.data_editor(
        edit_slice,
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key="rnas_edit_slice",
        column_config=col_cfg,
    )

    do_save = st.button("💾 Save selected edits", type="primary", disabled=not HAS["notes"])

    if do_save and HAS["notes"]:
        upd_sql = text(f"""
            UPDATE public.rnas
               SET {colmap['notes']} = COALESCE(:notes, {colmap['notes']})
             WHERE {colmap['code']} = :rna_code
        """)

        orig_all = st.session_state["_rnas_original"].set_index("rna_code")
        cur_rows = edited_slice.set_index("rna_code")
        to_update: List[Dict] = []

        for code, row in cur_rows.iterrows():
            old = orig_all.at[code, "notes"] if ("notes" in orig_all.columns) else None
            new = row.get("notes")
            if (pd.isna(old) and pd.isna(new)) or (old == new):
                continue
            to_update.append({"rna_code": code, "notes": (None if pd.isna(new) else new)})

        if not to_update:
            st.success("No changes detected.")
        else:
            n_upd = 0
            with _eng().begin() as cx:
                for rec in to_update:
                    cx.execute(upd_sql, rec)
                    n_upd += 1

            for rec in to_update:
                code = rec["rna_code"]; v = rec["notes"]
                st.session_state["_rnas_table"].loc[st.session_state["_rnas_table"]["rna_code"] == code, "notes"] = v
                st.session_state["_rnas_original"].loc[st.session_state["_rnas_original"]["rna_code"] == code, "notes"] = v

            st.success(f"Saved {n_upd} updated row(s).")

st.divider()

# ===== ADD NEW RNA (rna_code + notes only) ===================================
with st.expander("➕ Add new RNA"):
    with st.form("add_rna"):
        new_code = st.text_input("rna_code (required)", "")
        new_notes = st.text_area("notes", "") if HAS["notes"] else None
        submitted_add = st.form_submit_button("Insert")

    if submitted_add:
        code_ok = (new_code or "").strip()
        if not code_ok:
            st.error("rna_code is required.")
        else:
            cols, vals = [colmap["code"]], [":code"]
            params = {"code": code_ok}
            if HAS["notes"] and (new_notes or "").strip():
                cols += [colmap["notes"]]; vals += [":notes"]; params["notes"] = new_notes.strip()

            ins_sql = text(f"""
                INSERT INTO public.rnas ({', '.join(cols)})
                VALUES ({', '.join(vals)})
                ON CONFLICT ({colmap['code']}) DO NOTHING
            """)
            with _eng().begin() as cx:
                cx.execute(ins_sql, params)

            row = {
                "✓ Select": False,
                "rna_code": code_ok,
                "fusion_names": "",
                "fluor_names": "",
                "tag_names": "",
                "notes": params.get("notes","") if HAS["notes"] else "",
                "created_by": "",
                "created_at": pd.Timestamp.utcnow(),
            }
            for k in row.keys():
                if k not in st.session_state["_rnas_table"].columns:
                    st.session_state["_rnas_table"][k] = ""
                if k not in st.session_state["_rnas_original"].columns:
                    st.session_state["_rnas_original"][k] = ""
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
    data=st.session_state["_rnas_table"][ [c for c in view_cols if c in st.session_state["_rnas_table"].columns] ].to_csv(index=False).encode("utf-8"),
    file_name="overview_rnas.csv",
    type="secondary",
    use_container_width=True,
)