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

def _build_query(q: str, limit: int) -> tuple[str, dict]:
    """
    Build inline plasmid overview query with n_fusions, no supports_invitro_rna, no name.
    """
    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    params: dict = {"lim": int(limit)}
    where: list[str] = []

    base_cte = """
      WITH vp AS (
        SELECT
          p.code,
          COALESCE(p.nickname,'')   AS nickname,
          COALESCE(p.resistance,'') AS resistance,

          COALESCE(
            ARRAY_REMOVE(
              ARRAY_AGG(DISTINCT fl.fluor_code)
              FILTER (WHERE fl.fluor_code IS NOT NULL),
              NULL
            ),
            ARRAY[]::text[]
          ) AS fluors_arr,

          COALESCE(
            ARRAY_REMOVE(
              ARRAY_AGG(DISTINCT tg.tag_code)
              FILTER (WHERE tg.tag_code IS NOT NULL),
              NULL
            ),
            ARRAY[]::text[]
          ) AS tags_arr,

          COALESCE(
            ARRAY_REMOVE(
              ARRAY_AGG(
                DISTINCT CASE
                  WHEN tg.tag_code IS NULL THEN fl.fluor_code
                  ELSE CONCAT(fl.fluor_code,'::',tg.tag_code)
                END
              ) FILTER (WHERE fl.fluor_code IS NOT NULL),
              NULL
            ),
            ARRAY[]::text[]
          ) AS fusions_arr,

          p.created_at,
          NULL::text AS created_by,
          COALESCE(p.notes,'') AS notes
        FROM public.plasmids p
        LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
        LEFT JOIN public.fusions f               ON f.id = jpf.fusion_id
        LEFT JOIN public.fluors  fl              ON fl.id = f.fluor_id
        LEFT JOIN public.tags    tg              ON tg.id = f.tag_id
        GROUP BY p.code, p.nickname, p.resistance, p.created_at, p.notes
      )
    """

    field_map = {
        "code":       "vp.code",
        "nickname":   "vp.nickname",
        "fluors":     "array_to_string(vp.fluors_arr, ',')",
        "tags":       "array_to_string(vp.tags_arr, ',')",
        "fusions":    "array_to_string(vp.fusions_arr, ',')",
        "resistance": "vp.resistance",
        "notes":      "vp.notes",
    }
    haystack = (
        "concat_ws(' ', "
        "coalesce(vp.code,''), coalesce(vp.nickname,''), "
        "array_to_string(vp.fluors_arr, ','), array_to_string(vp.tags_arr, ','), "
        "array_to_string(vp.fusions_arr, ','), coalesce(vp.resistance,''), coalesce(vp.notes,''))"
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

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    body = f"""
      {base_cte}
      SELECT
        vp.code,
        vp.nickname,
        vp.fluors_arr  AS fluors,
        vp.tags_arr    AS tags,
        vp.fusions_arr AS fusions,
        COALESCE(cardinality(vp.fusions_arr), 0) AS n_fusions,
        vp.resistance,
        vp.created_by,
        vp.created_at,
        vp.notes
      FROM vp
      {where_sql}
      ORDER BY vp.code
      LIMIT :lim
    """
    return body, params

def _load_plasmids(q: str, limit: int) -> pd.DataFrame:
    sql, params = _build_query(q, limit)
    with _get_engine().begin() as cx:
        return pd.read_sql(text(sql), cx, params=params)

# === Filters form ===
with st.form("filters"):
    c1, c2 = st.columns([3,1])
    with c1:
        q = st.text_input("Search (supports code:, nickname:, fluors:, tags:, fusions:, resistance:)", "")
    with c2:
        limit = int(st.number_input("Limit", min_value=1, max_value=10000, value=1000, step=200))
    submitted = st.form_submit_button("Apply")

try:
    df = _load_plasmids(q, limit)
except Exception as e:
    st.error(f"Query error: {type(e).__name__}: {e}")
    with st.expander("Debug"):
        st.code(str(e))
    st.stop()

st.caption(f"{len(df)} rows")

# ===== READ-ONLY MASTER TABLE ================================================
view_cols = [
    "✓ Select",
    "code","nickname","fluors","tags","fusions","n_fusions",
    "resistance","created_by","created_at","notes"
]

UPDATABLE_COLS = ["nickname", "resistance", "notes"]

# Base view of the current query result
df_view = df.copy()
df_view.insert(0, "✓ Select", False)

# ---- Safe session_state initialization / refresh ----
def _sig_from(df_codes: pd.Series) -> str:
    return "|".join(df_codes.astype(str).tolist()) if not df_codes.empty else ""

new_sig = _sig_from(df_view.get("code", pd.Series([], dtype=str)))

if "_plasmids_table" not in st.session_state:
    st.session_state["_plasmids_table"]   = df_view.copy()
    st.session_state["_plasmids_original"] = df_view.copy()
    st.session_state["_plasmids_sig"]      = new_sig
else:
    if st.session_state.get("_plasmids_sig") != new_sig:
        st.session_state["_plasmids_table"]   = df_view.copy()
        st.session_state["_plasmids_original"] = df_view.copy()
        st.session_state["_plasmids_sig"]      = new_sig

# Render the read-only master table
ro = st.data_editor(
    st.session_state["_plasmids_table"],
    use_container_width=True,
    hide_index=True,
    height=520,
    num_rows="fixed",
    column_order=view_cols,
    column_config={
        "✓ Select":   st.column_config.CheckboxColumn("✓ Select", default=False),
        "code":       st.column_config.TextColumn("code", disabled=True),
        "nickname":   st.column_config.TextColumn("nickname", disabled=True),
        "fluors":     st.column_config.ListColumn("fluors",  disabled=True),
        "tags":       st.column_config.ListColumn("tags",    disabled=True),
        "fusions":    st.column_config.ListColumn("fusions", disabled=True),
        "n_fusions":  st.column_config.NumberColumn("n_fusions", disabled=True, format="%d"),
        "resistance": st.column_config.TextColumn("resistance", disabled=True),
        "created_by": st.column_config.TextColumn("created_by", disabled=True),
        "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
        "notes":      st.column_config.TextColumn("notes", disabled=True),
    },
    key="plasmids_ro",
)

if "✓ Select" in ro.columns:
    st.session_state["_plasmids_table"]["✓ Select"] = ro["✓ Select"].values
else:
    st.session_state["_plasmids_table"]["✓ Select"] = False

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
        "code":       st.column_config.TextColumn("code", disabled=True),
        "nickname":   st.column_config.TextColumn("nickname", disabled=("nickname" not in editable_cols)),
        "resistance": st.column_config.TextColumn("resistance", disabled=("resistance" not in editable_cols)),
        "notes":      st.column_config.TextColumn("notes", disabled=("notes" not in editable_cols)),
    }

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

    if do_save:
        orig_all = st.session_state["_plasmids_original"].set_index("code")
        cur_rows = edited_slice.set_index("code")
        to_update = []

        for code, row in cur_rows.iterrows():
            changed = {}
            for col in UPDATABLE_COLS:
                if col not in editable_cols: continue
                old = orig_all.at[code, col] if (code in orig_all.index and col in orig_all.columns) else None
                new = row.get(col)
                if (pd.isna(old) and pd.isna(new)) or (old == new):
                    continue
                changed[col] = None if pd.isna(new) else new
            if changed:
                changed["code"] = code
                to_update.append(changed)

        if not to_update:
            st.success("No changes detected.")
        else:
            upd_sql = text("""
                UPDATE public.plasmids
                   SET nickname  = COALESCE(:nickname, nickname),
                       resistance= COALESCE(:resistance, resistance),
                       notes     = COALESCE(:notes, notes)
                 WHERE code = :code
            """)

            n_upd = 0
            with _get_engine().begin() as cx:
                for rec in to_update:
                    payload = {
                        "code":       rec["code"],
                        "nickname":   rec.get("nickname"),
                        "resistance": rec.get("resistance"),
                        "notes":      rec.get("notes"),
                    }
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

# ===== ADD NEW PLASMID ========================================================
with st.expander("➕ Add new plasmid"):
    with st.form("add_plasmid"):
        new_code = st.text_input("code (required)", "")
        new_nick = st.text_input("nickname (required)", "")
        new_res  = st.text_input("resistance", "")
        new_notes = st.text_area("notes", "")
        submitted_add = st.form_submit_button("Insert")

    if submitted_add:
        code_ok = (new_code or "").strip()
        nick_ok = (new_nick or "").strip()
        if not code_ok or not nick_ok:
            st.error("Both code and nickname are required.")
        else:
            ins_sql = text("""
                INSERT INTO public.plasmids(code, nickname, resistance, notes, created_by)
                VALUES (:code, :nickname, :resistance, :notes, :by)
                ON CONFLICT (code) DO NOTHING
            """)
            by = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
            with _get_engine().begin() as cx:
                cx.execute(ins_sql, {
                    "code": code_ok,
                    "nickname": nick_ok,
                    "resistance": (new_res or None),
                    "notes": (new_notes or None),
                    "by": by,
                })

            row = {
                "✓ Select": False,
                "code": code_ok,
                "nickname": nick_ok,
                "fluors": [],
                "tags": [],
                "fusions": [],
                "n_fusions": 0,
                "resistance": (new_res or None),
                "created_by": by,
                "created_at": pd.Timestamp.utcnow(),
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