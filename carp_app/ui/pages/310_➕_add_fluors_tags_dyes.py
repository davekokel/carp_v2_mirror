from __future__ import annotations

import pathlib
import sys
from typing import Dict, List, Optional, Tuple

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
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Edit: Constructs & Markers",
    page_icon="🧬",
    layout="wide",
)
st.title("🧬 Edit: Constructs & Markers")


def _eng() -> Engine:
    return engine()


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


tab_constructs, tab_fluors, tab_tags, tab_dyes = st.tabs(
    ["Constructs", "Fluors", "Tags", "Dyes"]
)

# ────────────────────────────────────────────────────────
# Helpers for selectlists
# ────────────────────────────────────────────────────────

def _load_construct_choices(q: str | None, limit: int = 200) -> pd.DataFrame:
    where = ["1=1"]
    params: Dict[str, object] = {"lim": limit}

    if q:
        params["ql"] = f"%{q}%"
        where.append(
            "("
            "  c.code ILIKE :ql"
            " OR COALESCE(c.nickname,'') ILIKE :ql"
            " OR COALESCE(c.display_name,'') ILIKE :ql"
            " OR c.construct_code ILIKE :ql"
            " OR c.construct_name ILIKE :ql"
            " OR COALESCE(c.description,'') ILIKE :ql"
            ")"
        )

    where_sql = " AND ".join(where)
    sql = text(
        f"""
        SELECT
          c.id::text        AS id,
          c.code            AS code,
          c.nickname        AS nickname,
          c.display_name    AS display_name,
          c.construct_code  AS construct_code,
          c.construct_name  AS construct_name
        FROM public.constructs c
        WHERE {where_sql}
        ORDER BY c.display_name, c.construct_code
        LIMIT :lim;
        """
    )
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params=params)


def _load_fluor_choices(q: str | None, limit: int = 200) -> pd.DataFrame:
    where = ["1=1"]
    params: Dict[str, object] = {"lim": limit}
    if q:
        params["ql"] = f"%{q}%"
        where.append(
            "("
            "  code ILIKE :ql"
            " OR COALESCE(nickname,'') ILIKE :ql"
            " OR COALESCE(display_name,'') ILIKE :ql"
            " OR COALESCE(fluor_code,'') ILIKE :ql"
            " OR COALESCE(fluor_name,'') ILIKE :ql"
            ")"
        )
    where_sql = " AND ".join(where)
    sql = text(
        f"""
        SELECT
          id::text        AS id,
          code            AS code,
          nickname        AS nickname,
          display_name    AS display_name,
          fluor_code,
          fluor_name
        FROM public.fluors
        WHERE {where_sql}
        ORDER BY display_name, fluor_name, fluor_code
        LIMIT :lim;
        """
    )
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params=params)


def _load_tag_choices(q: str | None, limit: int = 200) -> pd.DataFrame:
    where = ["1=1"]
    params: Dict[str, object] = {"lim": limit}
    if q:
        params["ql"] = f"%{q}%"
        where.append(
            "("
            "  code ILIKE :ql"
            " OR COALESCE(nickname,'') ILIKE :ql"
            " OR COALESCE(display_name,'') ILIKE :ql"
            " OR tag_code ILIKE :ql"
            " OR tag_name ILIKE :ql"
            " OR COALESCE(localization,'') ILIKE :ql"
            ")"
        )
    where_sql = " AND ".join(where)
    sql = text(
        f"""
        SELECT
          id::text        AS id,
          code            AS code,
          nickname        AS nickname,
          display_name    AS display_name,
          tag_code,
          tag_name
        FROM public.tags
        WHERE {where_sql}
        ORDER BY display_name, tag_code
        LIMIT :lim;
        """
    )
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params=params)


def _load_dye_choices(q: str | None, limit: int = 200) -> pd.DataFrame:
    where = ["1=1"]
    params: Dict[str, object] = {"lim": limit}
    if q:
        params["ql"] = f"%{q}%"
        where.append(
            "("
            "  d.code ILIKE :ql"
            " OR COALESCE(d.nickname,'') ILIKE :ql"
            " OR COALESCE(d.display_name,'') ILIKE :ql"
            " OR d.dye_base_code ILIKE :ql"
            " OR d.name ILIKE :ql"
            " OR COALESCE(d.notes,'') ILIKE :ql"
            ")"
        )
    where_sql = " AND ".join(where)
    sql = text(
        f"""
        SELECT
          d.id::text        AS id,
          d.code            AS code,
          d.nickname        AS nickname,
          d.display_name    AS display_name,
          d.dye_base_code   AS dye_base_code,
          d.name            AS dye_name
        FROM public.dyes d
        WHERE {where_sql}
        ORDER BY d.display_name, d.dye_base_code
        LIMIT :lim;
        """
    )
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params=params)


# ════════════════════════════════════════════════════════
# TAB 1 — CONSTRUCTS (ADD / EDIT)
# ════════════════════════════════════════════════════════
with tab_constructs:
    st.subheader("Constructs (add / edit)")

    c_left, c_right = st.columns([1.1, 2.0])

    # ── left: picker ─────────────────────────────────────
    with c_left:
        st.caption("Pick an existing construct or start a new one.")
        q_pick = st.text_input(
            "Filter constructs",
            "",
            key="constructs_edit_filter",
            help="Search by code, nickname, display_name, base code, or name.",
        )
        df_choices = _load_construct_choices(_norm(q_pick))
        if df_choices.empty:
            st.info("No constructs match this filter.")
            selected_code = None
        else:
            options = [
                f"{row.display_name} [{row.construct_code}] ({row.code})"
                for _, row in df_choices.iterrows()
            ]
            codes = df_choices["code"].tolist()
            index = 0
            selected_opt = st.selectbox(
                "Existing constructs",
                ["(none — create new)"] + options,
                index=0,
                key="constructs_edit_select",
            )
            if selected_opt == "(none — create new)":
                selected_code = None
            else:
                idx = options.index(selected_opt)
                selected_code = codes[idx]

        st.markdown("---")
        new_clicked = st.button("➕ Start new construct", key="constructs_new_btn")

    # ── right: form ──────────────────────────────────────
    with c_right:
        st.caption("Construct details")

        init_vals: Dict[str, object] = {
            "code": "",
            "nickname": "",
            "display_name": "",
            "construct_code": "",
            "construct_name": "",
            "construct_kind": "",
            "resistance": "",
            "description": "",
            "inj_plasmid": False,
            "inj_rna": False,
            "inj_crispr": False,
        }

        if selected_code and not new_clicked:
            sql_one = text(
                """
                SELECT
                  id::text            AS id,
                  code,
                  nickname,
                  display_name,
                  construct_code,
                  construct_name,
                  construct_kind,
                  resistance,
                  description,
                  injection_use_plasmid AS inj_plasmid,
                  injection_use_rna     AS inj_rna,
                  injection_use_crispr  AS inj_crispr
                FROM public.constructs
                WHERE code = :code;
                """
            )
            with _eng().begin() as cx:
                row = pd.read_sql(sql_one, cx, params={"code": selected_code})
            if not row.empty:
                r = row.iloc[0]
                for k in init_vals.keys():
                    if k in r:
                        init_vals[k] = r[k]

        with st.form("construct_edit_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                code_display = st.text_input(
                    "code (CONSTR-…)",
                    value=str(init_vals["code"]),
                    disabled=True,
                )
                nickname = st.text_input(
                    "nickname",
                    value=str(init_vals["nickname"]),
                )
                display_name = st.text_input(
                    "display_name",
                    value=str(init_vals["display_name"]),
                )
                construct_code = st.text_input(
                    "base construct_code",
                    value=str(init_vals["construct_code"]),
                )
                construct_name = st.text_input(
                    "construct_name",
                    value=str(init_vals["construct_name"]),
                )
            with c2:
                construct_kind = st.text_input(
                    "construct_kind (physical kind, e.g. plasmid)",
                    value=str(init_vals["construct_kind"]),
                )
                resistance = st.text_input(
                    "resistance (e.g. amp, kan, …)",
                    value=str(init_vals["resistance"]),
                )
                description = st.text_area(
                    "description",
                    value=str(init_vals["description"]),
                    height=120,
                )
                inj_plasmid = st.checkbox(
                    "injection_use_plasmid",
                    value=bool(init_vals["inj_plasmid"]),
                )
                inj_rna = st.checkbox(
                    "injection_use_rna",
                    value=bool(init_vals["inj_rna"]),
                )
                inj_crispr = st.checkbox(
                    "injection_use_crispr",
                    value=bool(init_vals["inj_crispr"]),
                )

            submitted = st.form_submit_button(
                "💾 Save construct",
                type="primary",
            )

        if submitted:
            try:
                with _eng().begin() as cx:
                    if selected_code and not new_clicked:
                        cx.execute(
                            text(
                                """
                                UPDATE public.constructs
                                SET
                                  nickname        = :nickname,
                                  display_name    = :display_name,
                                  construct_code  = :construct_code,
                                  construct_name  = :construct_name,
                                  construct_kind  = :construct_kind,
                                  resistance      = :resistance,
                                  description     = :description,
                                  injection_use_plasmid = :inj_plasmid,
                                  injection_use_rna     = :inj_rna,
                                  injection_use_crispr  = :inj_crispr
                                WHERE code = :code;
                                """
                            ),
                            {
                                "code": code_display or selected_code,
                                "nickname": nickname or None,
                                "display_name": display_name or None,
                                "construct_code": construct_code or None,
                                "construct_name": construct_name or None,
                                "construct_kind": construct_kind or None,
                                "resistance": resistance or None,
                                "description": description or None,
                                "inj_plasmid": inj_plasmid,
                                "inj_rna": inj_rna,
                                "inj_crispr": inj_crispr,
                            },
                        )
                    else:
                        cx.execute(
                            text(
                                """
                                INSERT INTO public.constructs (
                                  nickname,
                                  display_name,
                                  construct_code,
                                  construct_name,
                                  construct_kind,
                                  resistance,
                                  description,
                                  injection_use_plasmid,
                                  injection_use_rna,
                                  injection_use_crispr
                                )
                                VALUES (
                                  :nickname,
                                  :display_name,
                                  :construct_code,
                                  :construct_name,
                                  :construct_kind,
                                  :resistance,
                                  :description,
                                  :inj_plasmid,
                                  :inj_rna,
                                  :inj_crispr
                                );
                                """
                            ),
                            {
                                "nickname": nickname or None,
                                "display_name": display_name or None,
                                "construct_code": construct_code or None,
                                "construct_name": construct_name or None,
                                "construct_kind": construct_kind or None,
                                "resistance": resistance or None,
                                "description": description or None,
                                "inj_plasmid": inj_plasmid,
                                "inj_rna": inj_rna,
                                "inj_crispr": inj_crispr,
                            },
                        )
                st.success("Construct saved.")
            except Exception as e:
                st.error(f"Error saving construct: {e}")

# ════════════════════════════════════════════════════════
# TAB 2 — FLUORS (ADD / EDIT)
# ════════════════════════════════════════════════════════
with tab_fluors:
    st.subheader("Fluors (add / edit)")

    c_left, c_right = st.columns([1.1, 2.0])

    with c_left:
        st.caption("Pick an existing fluor or start a new one.")
        q_pick_f = st.text_input(
            "Filter fluors",
            "",
            key="fluors_edit_filter",
        )
        df_f_choices = _load_fluor_choices(_norm(q_pick_f))
        if df_f_choices.empty:
            st.info("No fluors match this filter.")
            selected_f_code = None
        else:
            options_f = [
                f"{row.display_name} [{row.fluor_code}] ({row.code})"
                for _, row in df_f_choices.iterrows()
            ]
            codes_f = df_f_choices["code"].tolist()
            selected_opt_f = st.selectbox(
                "Existing fluors",
                ["(none — create new)"] + options_f,
                index=0,
                key="fluors_edit_select",
            )
            if selected_opt_f == "(none — create new)":
                selected_f_code = None
            else:
                idx = options_f.index(selected_opt_f)
                selected_f_code = codes_f[idx]

        st.markdown("---")
        new_f_clicked = st.button("➕ Start new fluor", key="fluors_new_btn")

    with c_right:
        st.caption("Fluor details")

        init_f: Dict[str, object] = {
            "code": "",
            "nickname": "",
            "display_name": "",
            "fluor_code": "",
            "fluor_name": "",
            "excitation_nm": 0,
            "emission_nm": 0,
            "alt_names": "",
            "notes": "",
        }

        if selected_f_code and not new_f_clicked:
            sql_one_f = text(
                """
                SELECT
                  id::text        AS id,
                  code,
                  nickname,
                  display_name,
                  fluor_code,
                  fluor_name,
                  excitation_nm,
                  emission_nm,
                  alt_names,
                  notes
                FROM public.fluors
                WHERE code = :code;
                """
            )
            with _eng().begin() as cx:
                row_f = pd.read_sql(sql_one_f, cx, params={"code": selected_f_code})
            if not row_f.empty:
                r = row_f.iloc[0]
                for k in init_f.keys():
                    if k in r and r[k] is not None:
                        if k == "alt_names":
                            # alt_names may be array or text
                            init_f[k] = (
                                ", ".join(r[k])
                                if isinstance(r[k], list)
                                else str(r[k])
                            )
                        else:
                            init_f[k] = r[k]

        with st.form("fluor_edit_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                f_code_display = st.text_input(
                    "code (FLUOR-…)",
                    value=str(init_f["code"]),
                    disabled=True,
                )
                f_nickname = st.text_input(
                    "nickname",
                    value=str(init_f["nickname"]),
                )
                f_display_name = st.text_input(
                    "display_name",
                    value=str(init_f["display_name"]),
                )
                f_fluor_code = st.text_input(
                    "fluor_code (domain code)",
                    value=str(init_f["fluor_code"]),
                )
                f_fluor_name = st.text_input(
                    "fluor_name",
                    value=str(init_f["fluor_name"]),
                )
            with c2:
                f_exc = st.number_input(
                    "excitation_nm",
                    min_value=0,
                    max_value=2000,
                    value=int(init_f["excitation_nm"] or 0),
                    step=1,
                )
                f_em = st.number_input(
                    "emission_nm",
                    min_value=0,
                    max_value=2000,
                    value=int(init_f["emission_nm"] or 0),
                    step=1,
                )
                f_alt = st.text_area(
                    "alt_names (comma-separated)",
                    value=str(init_f["alt_names"]),
                    height=80,
                )
                f_notes = st.text_area(
                    "notes",
                    value=str(init_f["notes"]),
                    height=80,
                )

            submitted_f = st.form_submit_button(
                "💾 Save fluor",
                type="primary",
            )

        if submitted_f:
            try:
                with _eng().begin() as cx:
                    if selected_f_code and not new_f_clicked:
                        cx.execute(
                            text(
                                """
                                UPDATE public.fluors
                                SET
                                  nickname      = :nickname,
                                  display_name  = :display_name,
                                  fluor_code    = :fluor_code,
                                  fluor_name    = :fluor_name,
                                  excitation_nm = :excitation_nm,
                                  emission_nm   = :emission_nm,
                                  alt_names     = CASE
                                    WHEN :alt_names IS NULL OR :alt_names = ''
                                      THEN NULL
                                    ELSE string_to_array(:alt_names, ',')
                                  END,
                                  notes         = :notes
                                WHERE code = :code;
                                """
                            ),
                            {
                                "code": f_code_display or selected_f_code,
                                "nickname": f_nickname or None,
                                "display_name": f_display_name or None,
                                "fluor_code": f_fluor_code or None,
                                "fluor_name": f_fluor_name or None,
                                "excitation_nm": int(f_exc) if f_exc else None,
                                "emission_nm": int(f_em) if f_em else None,
                                "alt_names": f_alt or None,
                                "notes": f_notes or None,
                            },
                        )
                    else:
                        cx.execute(
                            text(
                                """
                                INSERT INTO public.fluors (
                                  nickname,
                                  display_name,
                                  fluor_code,
                                  fluor_name,
                                  excitation_nm,
                                  emission_nm,
                                  alt_names,
                                  notes
                                )
                                VALUES (
                                  :nickname,
                                  :display_name,
                                  :fluor_code,
                                  :fluor_name,
                                  :excitation_nm,
                                  :emission_nm,
                                  CASE
                                    WHEN :alt_names IS NULL OR :alt_names = ''
                                      THEN NULL
                                    ELSE string_to_array(:alt_names, ',')
                                  END,
                                  :notes
                                );
                                """
                            ),
                            {
                                "nickname": f_nickname or None,
                                "display_name": f_display_name or None,
                                "fluor_code": f_fluor_code or None,
                                "fluor_name": f_fluor_name or None,
                                "excitation_nm": int(f_exc) if f_exc else None,
                                "emission_nm": int(f_em) if f_em else None,
                                "alt_names": f_alt or None,
                                "notes": f_notes or None,
                            },
                        )
                st.success("Fluor saved.")
            except Exception as e:
                st.error(f"Error saving fluor: {e}")

# ════════════════════════════════════════════════════════
# TAB 3 — TAGS (ADD / EDIT)
# ════════════════════════════════════════════════════════
with tab_tags:
    st.subheader("Tags (add / edit)")

    c_left, c_right = st.columns([1.1, 2.0])

    with c_left:
        st.caption("Pick an existing tag or start a new one.")
        q_pick_t = st.text_input(
            "Filter tags",
            "",
            key="tags_edit_filter",
        )
        df_t_choices = _load_tag_choices(_norm(q_pick_t))
        if df_t_choices.empty:
            st.info("No tags match this filter.")
            selected_t_code = None
        else:
            options_t = [
                f"{row.display_name} [{row.tag_code}] ({row.code})"
                for _, row in df_t_choices.iterrows()
            ]
            codes_t = df_t_choices["code"].tolist()
            selected_opt_t = st.selectbox(
                "Existing tags",
                ["(none — create new)"] + options_t,
                index=0,
                key="tags_edit_select",
            )
            if selected_opt_t == "(none — create new)":
                selected_t_code = None
            else:
                idx = options_t.index(selected_opt_t)
                selected_t_code = codes_t[idx]

        st.markdown("---")
        new_t_clicked = st.button("➕ Start new tag", key="tags_new_btn")

    with c_right:
        st.caption("Tag details")

        init_t: Dict[str, object] = {
            "code": "",
            "nickname": "",
            "display_name": "",
            "tag_code": "",
            "tag_name": "",
            "localization": "",
            "notes": "",
        }

        if selected_t_code and not new_t_clicked:
            sql_one_t = text(
                """
                SELECT
                  id::text        AS id,
                  code,
                  nickname,
                  display_name,
                  tag_code,
                  tag_name,
                  localization,
                  notes
                FROM public.tags
                WHERE code = :code;
                """
            )
            with _eng().begin() as cx:
                row_t = pd.read_sql(sql_one_t, cx, params={"code": selected_t_code})
            if not row_t.empty:
                r = row_t.iloc[0]
                for k in init_t.keys():
                    if k in r and r[k] is not None:
                        init_t[k] = r[k]

        with st.form("tag_edit_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                t_code_display = st.text_input(
                    "code (TAG-…)",
                    value=str(init_t["code"]),
                    disabled=True,
                )
                t_nickname = st.text_input(
                    "nickname",
                    value=str(init_t["nickname"]),
                )
                t_display_name = st.text_input(
                    "display_name",
                    value=str(init_t["display_name"]),
                )
                t_tag_code = st.text_input(
                    "tag_code (domain code)",
                    value=str(init_t["tag_code"]),
                )
                t_tag_name = st.text_input(
                    "tag_name",
                    value=str(init_t["tag_name"]),
                )
            with c2:
                t_loc = st.text_input(
                    "localization",
                    value=str(init_t["localization"]),
                )
                t_notes = st.text_area(
                    "notes",
                    value=str(init_t["notes"]),
                    height=100,
                )

            submitted_t = st.form_submit_button(
                "💾 Save tag",
                type="primary",
            )

        if submitted_t:
            try:
                with _eng().begin() as cx:
                    if selected_t_code and not new_t_clicked:
                        cx.execute(
                            text(
                                """
                                UPDATE public.tags
                                SET
                                  nickname     = :nickname,
                                  display_name = :display_name,
                                  tag_code     = :tag_code,
                                  tag_name     = :tag_name,
                                  localization = :localization,
                                  notes        = :notes
                                WHERE code = :code;
                                """
                            ),
                            {
                                "code": t_code_display or selected_t_code,
                                "nickname": t_nickname or None,
                                "display_name": t_display_name or None,
                                "tag_code": t_tag_code or None,
                                "tag_name": t_tag_name or None,
                                "localization": t_loc or None,
                                "notes": t_notes or None,
                            },
                        )
                    else:
                        cx.execute(
                            text(
                                """
                                INSERT INTO public.tags (
                                  nickname,
                                  display_name,
                                  tag_code,
                                  tag_name,
                                  localization,
                                  notes
                                )
                                VALUES (
                                  :nickname,
                                  :display_name,
                                  :tag_code,
                                  :tag_name,
                                  :localization,
                                  :notes
                                );
                                """
                            ),
                            {
                                "nickname": t_nickname or None,
                                "display_name": t_display_name or None,
                                "tag_code": t_tag_code or None,
                                "tag_name": t_tag_name or None,
                                "localization": t_loc or None,
                                "notes": t_notes or None,
                            },
                        )
                st.success("Tag saved.")
            except Exception as e:
                st.error(f"Error saving tag: {e}")

# ════════════════════════════════════════════════════════
# TAB 4 — DYES (ADD / EDIT)
# ════════════════════════════════════════════════════════
with tab_dyes:
    st.subheader("Dyes (add / edit)")

    c_left, c_right = st.columns([1.1, 2.0])

    with c_left:
        st.caption("Pick an existing dye or start a new one.")
        q_pick_d = st.text_input(
            "Filter dyes",
            "",
            key="dyes_edit_filter",
        )
        df_d_choices = _load_dye_choices(_norm(q_pick_d))
        if df_d_choices.empty:
            st.info("No dyes match this filter.")
            selected_d_code = None
        else:
            options_d = [
                f"{row.display_name} [{row.dye_base_code}] ({row.code})"
                for _, row in df_d_choices.iterrows()
            ]
            codes_d = df_d_choices["code"].tolist()
            selected_opt_d = st.selectbox(
                "Existing dyes",
                ["(none — create new)"] + options_d,
                index=0,
                key="dyes_edit_select",
            )
            if selected_opt_d == "(none — create new)":
                selected_d_code = None
            else:
                idx = options_d.index(selected_opt_d)
                selected_d_code = codes_d[idx]

        st.markdown("---")
        new_d_clicked = st.button("➕ Start new dye", key="dyes_new_btn")

    with c_right:
        st.caption("Dye details")

        init_d: Dict[str, object] = {
            "code": "",
            "nickname": "",
            "display_name": "",
            "dye_base_code": "",
            "dye_name": "",
            "notes": "",
            "linked_fluor_code": "",
            "fluor_name": "",
            "excitation_nm": None,
            "emission_nm": None,
        }

        if selected_d_code and not new_d_clicked:
            sql_one_d = text(
                """
                SELECT
                  d.id::text      AS id,
                  d.code,
                  d.nickname,
                  d.display_name,
                  d.dye_base_code,
                  d.name          AS dye_name,
                  d.notes,
                  f.fluor_code    AS linked_fluor_code,
                  f.fluor_name    AS fluor_name,
                  f.excitation_nm AS excitation_nm,
                  f.emission_nm   AS emission_nm
                FROM public.dyes d
                LEFT JOIN public.fluors f
                  ON f.id = d.fluor_id
                WHERE d.code = :code;
                """
            )
            with _eng().begin() as cx:
                row_d = pd.read_sql(sql_one_d, cx, params={"code": selected_d_code})
            if not row_d.empty:
                r = row_d.iloc[0]
                for k in init_d.keys():
                    if k in r and r[k] is not None:
                        init_d[k] = r[k]

        with st.form("dye_edit_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                d_code_display = st.text_input(
                    "code (DYE-…)",
                    value=str(init_d["code"]),
                    disabled=True,
                )
                d_nickname = st.text_input(
                    "nickname",
                    value=str(init_d["nickname"]),
                )
                d_display_name = st.text_input(
                    "display_name",
                    value=str(init_d["display_name"]),
                )
                d_base = st.text_input(
                    "dye_base_code (vendor or shorthand)",
                    value=str(init_d["dye_base_code"]),
                )
                d_name = st.text_input(
                    "name",
                    value=str(init_d["dye_name"]),
                )
            with c2:
                d_link_fluor = st.text_input(
                    "linked fluor_code (optional)",
                    value=str(init_d["linked_fluor_code"]),
                    help="If provided, dye will be linked to the fluor with this fluor_code.",
                )
                d_notes = st.text_area(
                    "notes",
                    value=str(init_d["notes"]),
                    height=100,
                )

            submitted_d = st.form_submit_button(
                "💾 Save dye",
                type="primary",
            )

        if submitted_d:
            try:
                with _eng().begin() as cx:
                    if selected_d_code and not new_d_clicked:
                        cx.execute(
                            text(
                                """
                                UPDATE public.dyes
                                SET
                                  nickname      = :nickname,
                                  display_name  = :display_name,
                                  dye_base_code = :dye_base_code,
                                  name          = :dye_name,
                                  notes         = :notes,
                                  fluor_id      = CASE
                                    WHEN :linked_fluor_code IS NULL OR :linked_fluor_code = ''
                                      THEN NULL
                                    ELSE (
                                      SELECT id
                                      FROM public.fluors
                                      WHERE fluor_code = :linked_fluor_code
                                      LIMIT 1
                                    )
                                  END
                                WHERE code = :code;
                                """
                            ),
                            {
                                "code": d_code_display or selected_d_code,
                                "nickname": d_nickname or None,
                                "display_name": d_display_name or None,
                                "dye_base_code": d_base or None,
                                "dye_name": d_name or None,
                                "notes": d_notes or None,
                                "linked_fluor_code": d_link_fluor or None,
                            },
                        )
                    else:
                        cx.execute(
                            text(
                                """
                                INSERT INTO public.dyes (
                                  nickname,
                                  display_name,
                                  dye_base_code,
                                  name,
                                  notes,
                                  fluor_id
                                )
                                VALUES (
                                  :nickname,
                                  :display_name,
                                  :dye_base_code,
                                  :dye_name,
                                  :notes,
                                  CASE
                                    WHEN :linked_fluor_code IS NULL OR :linked_fluor_code = ''
                                      THEN NULL
                                    ELSE (
                                      SELECT id
                                      FROM public.fluors
                                      WHERE fluor_code = :linked_fluor_code
                                      LIMIT 1
                                    )
                                  END
                                );
                                """
                            ),
                            {
                                "nickname": d_nickname or None,
                                "display_name": d_display_name or None,
                                "dye_base_code": d_base or None,
                                "dye_name": d_name or None,
                                "notes": d_notes or None,
                                "linked_fluor_code": d_link_fluor or None,
                            },
                        )
                st.success("Dye saved.")
            except Exception as e:
                st.error(f"Error saving dye: {e}")