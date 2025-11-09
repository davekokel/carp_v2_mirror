# carp_app/ui/pages/009_📤_upload_plasmids_overview.py
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os, shlex
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.lib.db import get_engine

st.set_page_config(page_title="CARP — Plasmids Overview", page_icon="🧪", layout="wide")

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp

sb, session, user = require_auth()
require_email_otp()

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

def _has_supports_flag() -> bool:
    with _get_engine().begin() as cx:
        return bool(cx.execute(text("""
            select exists (
              select 1
              from information_schema.columns
              where table_schema='public'
                and table_name='plasmids'
                and column_name='supports_invitro_rna'
            )
        """)).scalar())

HAS_SUPPORTS_FLAG = _has_supports_flag()

def _build_query(q: str, supports_only: bool, limit: int, has_flag: bool) -> tuple[str, dict]:
    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    params: dict = {"lim": int(limit)}
    where: list[str] = []

    field_map = {
        "code":       "vp.code",
        "name":       "vp.name",
        "nickname":   "vp.nickname",
        "fluors":     "array_to_string(vp.fluors_arr, ',')",
        "tags":       "array_to_string(vp.tags_arr, ',')",
        "fusions":    "array_to_string(vp.fusions_arr, ',')",
        "resistance": "vp.resistance",
        "notes":      "vp.notes",
    }
    haystack = (
        "concat_ws(' ', "
        "coalesce(vp.code,''), coalesce(vp.name,''), coalesce(vp.nickname,''), "
        "array_to_string(vp.fluors_arr, ','), array_to_string(vp.tags_arr, ','), array_to_string(vp.fusions_arr, ','), "
        "coalesce(vp.resistance,''), coalesce(vp.notes,''))"
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

    if has_flag and supports_only:
        where.append("p.supports_invitro_rna IS TRUE")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    if has_flag:
        sql = f"""
          SELECT
            vp.code,
            vp.name,
            vp.nickname,
            vp.fluors_arr  AS fluors,
            vp.tags_arr    AS tags,
            vp.fusions_arr AS fusions,
            vp.resistance,
            COALESCE(p.supports_invitro_rna, false) AS supports_invitro_rna,
            vp.created_by,
            vp.created_at,
            NULL::uuid AS rna_id,
            NULL::text AS rna_code,
            NULL::text AS rna_name,
            vp.notes
          FROM public.v_plasmids vp
          LEFT JOIN public.plasmids p
            ON p.code = vp.code
          {where_sql}
          ORDER BY vp.code
          LIMIT :lim
        """
    else:
        sql = f"""
          SELECT
            vp.code,
            vp.name,
            vp.nickname,
            vp.fluors_arr  AS fluors,
            vp.tags_arr    AS tags,
            vp.fusions_arr AS fusions,
            vp.resistance,
            false AS supports_invitro_rna,
            vp.created_by,
            vp.created_at,
            NULL::uuid AS rna_id,
            NULL::text AS rna_code,
            NULL::text AS rna_name,
            vp.notes
          FROM public.v_plasmids vp
          {where_sql}
          ORDER BY vp.code
          LIMIT :lim
        """
    return sql, params

def _load_plasmids(q: str, supports_only: bool, limit: int) -> pd.DataFrame:
    sql, params = _build_query(q, supports_only, limit, HAS_SUPPORTS_FLAG)
    with _get_engine().begin() as cx:
        return pd.read_sql(text(sql), cx, params=params)

with st.form("filters"):
    c1, c2, c3 = st.columns([2,2,1])
    with c1:
        q = st.text_input("Search (supports code:, name:, nickname:, fluors:, tags:, fusions:, resistance:)", "")
    with c2:
        supports_only = st.checkbox("Supports in-vitro RNA only", value=False, disabled=(not HAS_SUPPORTS_FLAG))
        if not HAS_SUPPORTS_FLAG:
            st.caption("⚠️ This DB has no plasmids.supports_invitro_rna; filter disabled.")
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

# ===== READ-ONLY MASTER TABLE ================================================
view_cols = [
    "✓ Select",
    "code","name","nickname","fluors","tags","fusions",
    "resistance","supports_invitro_rna",
    "rna_code","rna_name","created_by","created_at","notes"
]

UPDATABLE_COLS = ["name", "nickname", "resistance", "notes"]
if HAS_SUPPORTS_FLAG:
    UPDATABLE_COLS.append("supports_invitro_rna")

df_view = df.copy()
df_view.insert(0, "✓ Select", False)

if "_plasmids_original" not in st.session_state:
    st.session_state["_plasmids_original"] = df_view.copy()

sig = "|".join(df_view.get("code", pd.Series([], dtype=str)).astype(str).tolist())
if st.session_state.get("_plasmids_sig") != sig:
    st.session_state["_plasmids_sig"] = sig
    st.session_state["_plasmids_table"] = df_view.copy()
    st.session_state["_plasmids_original"] = df_view.copy()

ro = st.data_editor(
    st.session_state["_plasmids_table"],
    use_container_width=True,
    hide_index=True,
    height=520,
    num_rows="fixed",  # lock the main grid
    column_order=view_cols,
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
        "code":      st.column_config.TextColumn("code", disabled=True),
        "name":      st.column_config.TextColumn("name", disabled=True),
        "nickname":  st.column_config.TextColumn("nickname", disabled=True),
        "fluors":    st.column_config.ListColumn("fluors",  disabled=True),
        "tags":      st.column_config.ListColumn("tags",    disabled=True),
        "fusions":   st.column_config.ListColumn("fusions", disabled=True),
        "resistance": st.column_config.TextColumn("resistance", disabled=True),
        "supports_invitro_rna": st.column_config.CheckboxColumn("supports_invitro_rna", disabled=True),
        "rna_code":  st.column_config.TextColumn("rna_code", disabled=True),
        "rna_name":  st.column_config.TextColumn("rna_name", disabled=True),
        "created_by": st.column_config.TextColumn("created_by", disabled=True),
        "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
        "notes":     st.column_config.TextColumn("notes", disabled=True),
    },
    key="plasmids_ro",
)
st.session_state["_plasmids_table"]["✓ Select"] = ro["✓ Select"].values

st.divider()

# ===== EDIT SELECTION PANEL ===================================================
st.subheader("Edit selection")

cL, cR = st.columns([2,2])
with cL:
    editable_cols = st.multiselect(
        "1) Choose which columns are editable",
        options=UPDATABLE_COLS,
        help="Only these columns will be editable below."
    )
with cR:
    sel_mask = st.session_state["_plasmids_table"]["✓ Select"] == True
    sel_codes = st.session_state["_plasmids_table"].loc[sel_mask, "code"].dropna().astype(str).tolist()
    st.metric("Selected rows", len(sel_codes))

if len(sel_codes) == 0 or len(editable_cols) == 0:
    st.info("Select at least one row in the table above and choose one or more editable columns.")
else:
    base_all = st.session_state["_plasmids_table"].set_index("code")
    edit_slice = base_all.loc[sel_codes].reset_index()

    col_cfg = {
        "code": st.column_config.TextColumn("code", disabled=True),
        "name": st.column_config.TextColumn("name", disabled=("name" not in editable_cols)),
        "nickname": st.column_config.TextColumn("nickname", disabled=("nickname" not in editable_cols)),
        "resistance": st.column_config.TextColumn("resistance", disabled=("resistance" not in editable_cols)),
        "notes": st.column_config.TextColumn("notes", disabled=("notes" not in editable_cols)),
    }
    if HAS_SUPPORTS_FLAG:
        col_cfg["supports_invitro_rna"] = st.column_config.CheckboxColumn(
            "supports_invitro_rna", disabled=("supports_invitro_rna" not in editable_cols)
        )

    st.caption("Edit the selected rows/columns below, then save.")
    edited_slice = st.data_editor(
        edit_slice[["code"] + sorted(set(editable_cols))],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="plasmids_edit_slice",
        column_config=col_cfg,
    )

    do_save = st.button("💾 Save selected edits", type="primary")

    def _normalize_bool(v):
        if isinstance(v, bool): return v
        if v in [None, "", "null", "NULL"]: return None
        s = str(v).strip().lower()
        if s in ("t","true","1","yes","y","on"): return True
        if s in ("f","false","0","no","n","off"): return False
        return None

    if do_save:
        orig_all = st.session_state["_plasmids_original"].set_index("code")
        cur_rows = edited_slice.set_index("code")
        to_update = []

        for code, row in cur_rows.iterrows():
            changed = {}
            for col in editable_cols:
                old = orig_all.at[code, col] if (code in orig_all.index and col in orig_all.columns) else None
                new = row.get(col)
                if col == "supports_invitro_rna":
                    old = _normalize_bool(old)
                    new = _normalize_bool(new)
                if (pd.isna(old) and pd.isna(new)) or (old == new):
                    continue
                changed[col] = None if pd.isna(new) else new
            if changed:
                changed["code"] = code
                to_update.append(changed)

        if not to_update:
            st.success("No changes detected.")
        else:
            if HAS_SUPPORTS_FLAG:
                upd_sql = text("""
                    UPDATE public.plasmids
                       SET name = COALESCE(:name, name),
                           nickname = COALESCE(:nickname, nickname),
                           resistance = COALESCE(:resistance, resistance),
                           notes = COALESCE(:notes, notes),
                           supports_invitro_rna = COALESCE(:supports_invitro_rna, supports_invitro_rna)
                     WHERE code = :code
                """)
            else:
                upd_sql = text("""
                    UPDATE public.plasmids
                       SET name = COALESCE(:name, name),
                           nickname = COALESCE(:nickname, nickname),
                           resistance = COALESCE(:resistance, resistance),
                           notes = COALESCE(:notes, notes)
                     WHERE code = :code
                """)

            n_upd = 0
            with _get_engine().begin() as cx:
                for rec in to_update:
                    payload = {
                        "code": rec["code"],
                        "name": rec.get("name"),
                        "nickname": rec.get("nickname"),
                        "resistance": rec.get("resistance"),
                        "notes": rec.get("notes"),
                    }
                    if HAS_SUPPORTS_FLAG:
                        payload["supports_invitro_rna"] = _normalize_bool(rec.get("supports_invitro_rna"))
                    cx.execute(upd_sql, payload)
                    n_upd += 1

            for rec in to_update:
                for k, v in rec.items():
                    if k == "code": continue
                    st.session_state["_plasmids_table"].loc[
                        st.session_state["_plasmids_table"]["code"] == rec["code"], k
                    ] = v
                    st.session_state["_plasmids_original"].loc[
                        st.session_state["_plasmids_original"]["code"] == rec["code"], k
                    ] = v

            st.success(f"Saved {n_upd} updated row(s).")

st.divider()

# ===== ADD NEW PLASMID (guarded form) ========================================
with st.expander("➕ Add new plasmid"):
    with st.form("add_plasmid"):
        new_code = st.text_input("code (required)", "")
        new_name = st.text_input("name (required)", "")
        new_nick = st.text_input("nickname", "")
        new_res  = st.text_input("resistance", "")
        new_notes = st.text_area("notes", "")
        if HAS_SUPPORTS_FLAG:
            new_supports = st.checkbox("supports_invitro_rna", value=False)
        submitted_add = st.form_submit_button("Insert")

    if submitted_add:
        code_ok = (new_code or "").strip()
        name_ok = (new_name or "").strip()
        if not code_ok or not name_ok:
            st.error("Both code and name are required.")
        else:
            if HAS_SUPPORTS_FLAG:
                ins_sql = text("""
                    INSERT INTO public.plasmids(code, name, nickname, resistance, notes, created_by, supports_invitro_rna)
                    VALUES (:code, :name, :nickname, :resistance, :notes, :by, :supports)
                    ON CONFLICT (code) DO NOTHING
                """)
            else:
                ins_sql = text("""
                    INSERT INTO public.plasmids(code, name, nickname, resistance, notes, created_by)
                    VALUES (:code, :name, :nickname, :resistance, :notes, :by)
                    ON CONFLICT (code) DO NOTHING
                """)

            by = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
            with _get_engine().begin() as cx:
                params = {
                    "code": code_ok,
                    "name": name_ok,
                    "nickname": (new_nick or None),
                    "resistance": (new_res or None),
                    "notes": (new_notes or None),
                    "by": by,
                }
                if HAS_SUPPORTS_FLAG:
                    params["supports"] = bool(new_supports)
                cx.execute(ins_sql, params)

            row = {
                "✓ Select": False,
                "code": code_ok,
                "name": name_ok,
                "nickname": (new_nick or None),
                "fluors": [],
                "tags": [],
                "fusions": [],
                "resistance": (new_res or None),
                "supports_invitro_rna": bool(new_supports) if HAS_SUPPORTS_FLAG else False,
                "rna_code": None, "rna_name": None,
                "created_by": by, "created_at": pd.Timestamp.utcnow(),
                "notes": (new_notes or None),
            }
            st.session_state["_plasmids_table"] = pd.concat(
                [st.session_state["_plasmids_table"], pd.DataFrame([row])],
                ignore_index=True
            )
            st.session_state["_plasmids_original"] = pd.concat(
                [st.session_state["_plasmids_original"], pd.DataFrame([row])],
                ignore_index=True
            )
            st.success(f"Inserted plasmid {code_ok}.")