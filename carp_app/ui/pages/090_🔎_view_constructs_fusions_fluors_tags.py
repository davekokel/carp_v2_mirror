from __future__ import annotations

import shlex
import pathlib
import sys
from typing import Dict, Any, List, Optional

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
    def require_app_unlock() -> None:
        ...
from carp_app.ui.lib.page_engine import engine

# ───────── auth & page ─────────
st.set_page_config(
    page_title="CARP — Overview: Constructs • Fusions • Fluors • Tags",
    page_icon="🔎",
    layout="wide",
)

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.title("🔎 Overview: Constructs • Fusions • Fluors • Tags")


def _eng() -> Engine:
    return engine()


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


tab_constructs, tab_fusions, tab_fluors, tab_tags = st.tabs(
    ["Constructs", "Fusions", "Fluors", "Tags"]
)

# ════════════════════════════════════════════════════════
# TAB 1 — CONSTRUCTS
# ════════════════════════════════════════════════════════
with tab_constructs:
    st.subheader("Constructs")

    with st.form("construct_filters_cf", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns([3, 1.3, 1.5, 0.8])
        with c1:
            q_raw = st.text_input(
                "Search (code / nickname / display_name / kind / resistance / description / markers)",
                "",
            )
        with c2:
            kind_choice = st.selectbox(
                "Kind (physical)",
                ["(any)", "plasmid"],
                index=0,
            )
        with c3:
            inj_mode = st.selectbox(
                "Injection usage",
                ["(any)", "plasmid", "rna", "crispr"],
                index=0,
            )
        with c4:
            lim_constructs = int(
                st.number_input(
                    "Limit",
                    min_value=50,
                    max_value=5000,
                    value=1000,
                    step=50,
                    key="constructs_cf_limit",
                )
            )
        _ = st.form_submit_button("Apply")

    q = _norm(q_raw)
    kind_token = kind_choice if kind_choice != "(any)" else None
    inj_token = inj_mode if inj_mode != "(any)" else None

    where = ["1=1"]
    params: Dict[str, object] = {"lim": lim_constructs}

    if q:
        params["ql"] = f"%{q}%"
        where.append(
            "("
            "  c.code ILIKE :ql"
            " OR COALESCE(c.nickname,'') ILIKE :ql"
            " OR COALESCE(c.display_name,'') ILIKE :ql"
            " OR COALESCE(v.construct_kind,'') ILIKE :ql"
            " OR COALESCE(v.resistance,'') ILIKE :ql"
            " OR COALESCE(v.description,'') ILIKE :ql"
            " OR COALESCE(v.fusion_pretty,'') ILIKE :ql"
            " OR COALESCE(v.organelle_fluors,'') ILIKE :ql"
            ")"
        )

    if kind_token:
        params["kind_like"] = f"%{kind_token}%"
        where.append("v.construct_kind ILIKE :kind_like")

    if inj_token == "plasmid":
        where.append("v.injection_use_plasmid IS TRUE")
    elif inj_token == "rna":
        where.append("v.injection_use_rna IS TRUE")
    elif inj_token == "crispr":
        where.append("v.injection_use_crispr IS TRUE")

    where_sql = " AND ".join(where)

    sql_constructs = text(
        f"""
        SELECT
          c.id::text              AS id,
          c.code                  AS code,
          c.nickname              AS nickname,
          c.display_name          AS display_name,
          v.construct_code        AS legacy_construct_code,
          v.construct_kind        AS construct_kind,
          v.resistance            AS resistance,
          v.description           AS description,
          v.n_fusions             AS n_fusions,
          v.fusion_pretty         AS fusion_pretty,
          v.organelle_fluors      AS organelle_fluors,
          v.injection_use_plasmid AS injection_use_plasmid,
          v.injection_use_rna     AS injection_use_rna,
          v.injection_use_crispr  AS injection_use_crispr,
          v.created_at            AS created_at
        FROM public.v_constructs_overview v
        JOIN public.constructs c
          ON c.construct_code = v.construct_code
        WHERE {where_sql}
        ORDER BY v.created_at DESC NULLS LAST, c.code
        LIMIT :lim;
        """
    )

    with _eng().begin() as cx:
        df_constructs = pd.read_sql(sql_constructs, cx, params=params)

    if df_constructs.empty:
        st.info("No constructs match these filters.")
    else:
        for col in df_constructs.select_dtypes(include="object").columns:
            df_constructs[col] = df_constructs[col].fillna("")

        st.caption(f"{len(df_constructs)} construct(s)")

        view_constructs = pd.DataFrame(
            {
                "code": df_constructs["code"],
                "nickname": df_constructs["nickname"],
                "display_name": df_constructs["display_name"],
                "kind": df_constructs["construct_kind"],
                "legacy_construct_code": df_constructs["legacy_construct_code"],
                "resistance": df_constructs["resistance"],
                "description": df_constructs["description"],
                "linked_markers": df_constructs["fusion_pretty"],
                "organelle_fluors": df_constructs["organelle_fluors"],
                "n_fusions": df_constructs["n_fusions"],
                "inj_plasmid": df_constructs["injection_use_plasmid"].fillna(False),
                "inj_rna": df_constructs["injection_use_rna"].fillna(False),
                "inj_crispr": df_constructs["injection_use_crispr"].fillna(False),
                "created_at": df_constructs["created_at"],
                "id": df_constructs["id"],
            }
        )

        view_constructs.insert(0, "✓ Select", False)

        grid_constructs = st.data_editor(
            view_constructs,
            key="constructs_overview_cf",
            hide_index=True,
            num_rows="fixed",
            width="stretch",
            column_config={
                "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
                "code": st.column_config.TextColumn("code (CONSTR-…)", disabled=True),
                "nickname": st.column_config.TextColumn("nickname", disabled=True),
                "display_name": st.column_config.TextColumn(
                    "display_name", disabled=True, width="large"
                ),
                "kind": st.column_config.TextColumn("kind", disabled=True),
                "legacy_construct_code": st.column_config.TextColumn(
                    "legacy construct_code", disabled=True
                ),
                "resistance": st.column_config.TextColumn(
                    "resistance", disabled=True
                ),
                "description": st.column_config.TextColumn(
                    "description", disabled=True, width="large"
                ),
                "linked_markers": st.column_config.TextColumn(
                    "fusions fluor-tag(pos)", disabled=True, width="large"
                ),
                "organelle_fluors": st.column_config.TextColumn(
                    "organelle-fluors", disabled=True, width="large"
                ),
                "n_fusions": st.column_config.NumberColumn(
                    "n_fusions", disabled=True
                ),
                "inj_plasmid": st.column_config.CheckboxColumn(
                    "inj: plasmid", disabled=True
                ),
                "inj_rna": st.column_config.CheckboxColumn(
                    "inj: rna", disabled=True
                ),
                "inj_crispr": st.column_config.CheckboxColumn(
                    "inj: crispr", disabled=True
                ),
                "created_at": st.column_config.DatetimeColumn(
                    "created_at", disabled=True
                ),
                "id": st.column_config.TextColumn("id", disabled=True),
            },
        )

        st.divider()
        st.subheader("Construct details")

        selected_idxs: List[int] = []
        if "✓ Select" in grid_constructs.columns:
            selected_idxs = (
                grid_constructs.index[grid_constructs["✓ Select"] == True]
                .to_series()
                .tolist()
            )

        if not selected_idxs:
            st.info("Select one or more constructs above to see details.")
        elif len(selected_idxs) == 1:
            row = grid_constructs.loc[selected_idxs[0]]
            tab1, tab2 = st.tabs(["Overview", "Markers"])
            with tab1:
                st.write(
                    {
                        "code": row["code"],
                        "nickname": row["nickname"],
                        "display_name": row["display_name"],
                        "kind": row["kind"],
                        "legacy_construct_code": row["legacy_construct_code"],
                        "resistance": row["resistance"],
                        "description": row["description"],
                        "inj_plasmid": bool(row["inj_plasmid"]),
                        "inj_rna": bool(row["inj_rna"]),
                        "inj_crispr": bool(row["inj_crispr"]),
                    }
                )
            with tab2:
                st.write(
                    {
                        "linked_markers": row["linked_markers"],
                        "organelle_fluors": row["organelle_fluors"],
                    }
                )
        else:
            subset = grid_constructs.loc[selected_idxs].reset_index(drop=True)
            st.write("Summary for selected constructs:")
            st.dataframe(
                subset[
                    [
                        "kind",
                        "code",
                        "nickname",
                        "display_name",
                        "n_fusions",
                        "inj_plasmid",
                        "inj_rna",
                        "inj_crispr",
                    ]
                ],
                width="stretch",
            )

        st.download_button(
            "⬇︎ Download constructs (CSV)",
            data=df_constructs.to_csv(index=False).encode("utf-8"),
            file_name="constructs_overview_v11.csv",
            type="secondary",
            mime="text/csv",
        )

# ════════════════════════════════════════════════════════
# TAB 2 — FUSIONS
# ════════════════════════════════════════════════════════
with tab_fusions:
    st.subheader("Fusions")

    with st.form("fusion_filters_cf", clear_on_submit=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            q_raw_fus = st.text_input(
                "Search (supports fluor:, tag:, pos:, name:, -negation)",
                "",
            )
        with c2:
            lim_fusions = int(
                st.number_input(
                    "Limit (fusions)",
                    min_value=50,
                    max_value=5000,
                    value=1500,
                    step=100,
                    key="fusions_cf_limit",
                )
            )
        _ = st.form_submit_button("Apply", key="fusions_cf_apply")

    q_fus = _norm(q_raw_fus) or ""

    def _build_fusion_query(q: str, limit: int) -> tuple[str, Dict[str, Any]]:
        tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
        params: Dict[str, Any] = {"lim": int(limit)}
        where: List[str] = []

        c_fluor = "fluor_label"
        c_tag = "tag_label"
        c_pos = "tag_pos"
        c_name = "fusion_name"

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
                    where.append(
                        f"{'NOT ' if neg else ''}{field_map[k]} ILIKE :{key}"
                    )
                    continue
            key = f"p{i}"
            params[key] = f"%{core}%"
            where.append(f"{'NOT ' if neg else ''}{haystack} ILIKE :{key}")

        where_sql = "WHERE " + " AND ".join(where) if where else ""

        sql = f"""
        WITH fusions_core AS (
          SELECT
            f.id::text AS id,
            COALESCE(f.display_name, f.nickname, f.id::text) AS fusion_name,
            COALESCE(fl.nickname, fl.display_name, fl.code) AS fluor_label,
            COALESCE(tg.nickname, tg.display_name, tg.code) AS tag_label,
            f.tag_pos,
            COUNT(DISTINCT cf.construct_id) AS n_constructs,
            COALESCE(f.created_at, MIN(cf.created_at)) AS created_at
          FROM public.fusions f
          LEFT JOIN public.fluors fl
            ON fl.id = f.fluor_id
          LEFT JOIN public.tags tg
            ON tg.id = f.tag_id
          LEFT JOIN public.construct_fusions cf
            ON cf.fusion_id = f.id
          GROUP BY
            f.id,
            f.display_name,
            f.nickname,
            fl.nickname,
            fl.display_name,
            fl.code,
            tg.nickname,
            tg.display_name,
            tg.code,
            f.tag_pos,
            f.created_at
        )
        SELECT
          id,
          fusion_name,
          fluor_label AS fluor,
          tag_label   AS tag,
          tag_pos,
          n_constructs,
          created_at
        FROM fusions_core
        {where_sql}
        ORDER BY
          n_constructs DESC,
          fluor,
          tag     NULLS FIRST,
          tag_pos NULLS FIRST,
          created_at DESC
        LIMIT :lim;
        """

        return sql, params

    def _load_fusions(q: str, lim: int) -> pd.DataFrame:
        sql, params = _build_fusion_query(q, lim)
        with _eng().begin() as cx:
            df = pd.read_sql(text(sql), cx, params=params)
        for c in df.select_dtypes(include=["object", "string"]).columns:
            df[c] = df[c].astype("string").fillna("")
        return df

    try:
        df_fusions = _load_fusions(q_fus, lim_fusions)
    except Exception as e:
        st.error(f"Query error while loading fusions: {type(e).__name__}: {e}")
        st.stop()

    st.caption(f"{len(df_fusions)} fusion(s)")

    view_fusions = df_fusions.copy()
    view_fusions.insert(0, "✓ Select", False)

    grid_fusions = st.data_editor(
        view_fusions,
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        key="fusions_overview_cf",
        column_order=[
            "✓ Select",
            "fusion_name",
            "fluor",
            "tag",
            "tag_pos",
            "n_constructs",
            "created_at",
        ],
        column_config={
            "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
            "fusion_name": st.column_config.TextColumn("Fusion", disabled=True),
            "fluor": st.column_config.TextColumn("Fluor", disabled=True),
            "tag": st.column_config.TextColumn("Tag", disabled=True),
            "tag_pos": st.column_config.TextColumn("Pos", disabled=True),
            "n_constructs": st.column_config.NumberColumn(
                "Constructs", disabled=True
            ),
            "created_at": st.column_config.DatetimeColumn(
                "Created", disabled=True
            ),
        },
    )

    st.divider()
    st.subheader("Constructs containing selected fusion")

    selected_ids: List[str] = []
    fusion_names: Dict[str, str] = {}

    if isinstance(grid_fusions, pd.DataFrame) and "✓ Select" in grid_fusions.columns:
        sel = grid_fusions.loc[grid_fusions["✓ Select"] == True]
        if not sel.empty and "id" in sel.columns:
            selected_ids = sel["id"].astype(str).tolist()
            fusion_names = dict(zip(sel["id"].astype(str), sel["fusion_name"]))

    if len(selected_ids) == 1:
        fusion_id = selected_ids[0]
        fusion_label = fusion_names.get(fusion_id, fusion_id)

        with _eng().begin() as cx:
            constructs_df = pd.read_sql(
                text(
                    """
                    SELECT
                      c.code       AS construct_code,
                      c.display_name,
                      c.nickname,
                      c.construct_kind,
                      c.created_at
                    FROM public.construct_fusions cf
                    JOIN public.constructs c
                      ON c.id = cf.construct_id
                    WHERE cf.fusion_id = :fid::uuid
                    ORDER BY c.created_at DESC NULLS LAST, c.code
                    """
                ),
                cx,
                params={"fid": fusion_id},
            )

        st.subheader(f"Constructs containing: {fusion_label}")
        if constructs_df.empty:
            st.info("No constructs linked to this fusion.")
        else:
            st.dataframe(
                constructs_df[
                    [
                        "construct_code",
                        "display_name",
                        "nickname",
                        "construct_kind",
                        "created_at",
                    ]
                ],
                hide_index=True,
                width="stretch",
            )
            st.download_button(
                "⬇︎ Download constructs (CSV)",
                data=constructs_df.to_csv(index=False).encode("utf-8"),
                file_name=f"constructs_for_fusion_{fusion_label}.csv",
                type="secondary",
            )
    elif len(selected_ids) > 1:
        st.info("Select exactly one fusion to preview its constructs.")
    else:
        st.caption("Tip: check a fusion row above to preview its constructs.")

    st.download_button(
        "⬇︎ Download full fusion table (CSV)",
        data=df_fusions.to_csv(index=False).encode("utf-8"),
        file_name="fusions_overview_v11.csv",
        type="secondary",
        mime="text/csv",
    )

# ════════════════════════════════════════════════════════
# TAB 3 — FLUORS
# ════════════════════════════════════════════════════════
with tab_fluors:
    st.subheader("Fluors")

    with st.form("fluor_filters_cf", clear_on_submit=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            q_raw_f = st.text_input(
                "Search (code / nickname / display_name / alt_names / notes)",
                "",
                key="fluors_cf_search",
            )
        with c2:
            lim_f = int(
                st.number_input(
                    "Limit (fluors)",
                    min_value=50,
                    max_value=5000,
                    value=1000,
                    step=50,
                    key="fluors_cf_limit",
                )
            )
        _ = st.form_submit_button("Apply", key="fluors_cf_apply")

    q_f = _norm(q_raw_f)
    q_f_param = q_f or None

    sql_fluors = text(
        """
        SELECT
          id::text                        AS id,
          code                            AS code,
          COALESCE(nickname,'')           AS nickname,
          COALESCE(display_name,'')       AS display_name,
          COALESCE(excitation_nm,0)::int  AS excitation_nm,
          COALESCE(emission_nm,0)::int    AS emission_nm,
          COALESCE(
            CASE
              WHEN pg_typeof(alt_names)::text = 'text[]'
                THEN array_to_string(alt_names, ', ')
              ELSE alt_names::text
            END, ''
          )                                AS alt_names,
          COALESCE(notes,'')               AS notes
        FROM public.fluors
        WHERE (
          :q IS NULL
          OR code                      ILIKE :ql
          OR COALESCE(nickname,'')     ILIKE :ql
          OR COALESCE(display_name,'') ILIKE :ql
          OR COALESCE(notes,'')        ILIKE :ql
          OR COALESCE(
               CASE
                 WHEN pg_typeof(alt_names)::text = 'text[]'
                   THEN array_to_string(alt_names, ',')
                 ELSE alt_names::text
               END,''
             ) ILIKE :ql
        )
        ORDER BY display_name, code
        LIMIT :lim;
        """
    )

    params_f = {
        "q": q_f_param,
        "ql": f"%{q_f}%" if q_f else None,
        "lim": lim_f,
    }

    with _eng().begin() as cx:
        df_f = pd.read_sql(sql_fluors, cx, params=params_f)

    if df_f.empty:
        st.info("No fluors match these filters.")
    else:
        df_f = df_f.fillna("")
        st.caption(f"{len(df_f)} fluor(s)")

        view_f = pd.DataFrame(
            {
                "code": df_f["code"],
                "nickname": df_f["nickname"],
                "display_name": df_f["display_name"],
                "excitation_nm": df_f["excitation_nm"],
                "emission_nm": df_f["emission_nm"],
                "alt_names": df_f["alt_names"],
                "notes": df_f["notes"],
                "id": df_f["id"],
            }
        )
        view_f.insert(0, "✓ Select", False)

        grid_f = st.data_editor(
            view_f,
            key="fluors_overview_cf",
            hide_index=True,
            num_rows="fixed",
            width="stretch",
            column_config={
                "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
                "code": st.column_config.TextColumn("code (FLUOR-…)", disabled=True),
                "nickname": st.column_config.TextColumn("nickname", disabled=True),
                "display_name": st.column_config.TextColumn(
                    "display_name", disabled=True
                ),
                "excitation_nm": st.column_config.NumberColumn(
                    "Excitation (nm)", disabled=True
                ),
                "emission_nm": st.column_config.NumberColumn(
                    "Emission (nm)", disabled=True
                ),
                "alt_names": st.column_config.TextColumn(
                    "Alt names", disabled=True
                ),
                "notes": st.column_config.TextColumn("Notes", disabled=True),
                "id": st.column_config.TextColumn("ID", disabled=True),
            },
        )

        st.divider()
        st.subheader("Fluor details")

        sel_f_idxs: List[int] = []
        if "✓ Select" in grid_f.columns:
            sel_f_idxs = (
                grid_f.index[grid_f["✓ Select"] == True].to_series().tolist()
            )

        if not sel_f_idxs:
            st.info("Select one or more fluors above to see details.")
        elif len(sel_f_idxs) == 1:
            row = grid_f.loc[sel_f_idxs[0]]
            tab1, tab2 = st.tabs(["Overview", "Spectra"])
            with tab1:
                st.write(
                    {
                        "code": row["code"],
                        "nickname": row["nickname"],
                        "display_name": row["display_name"],
                        "alt_names": row["alt_names"],
                        "notes": row["notes"],
                    }
                )
            with tab2:
                st.write(
                    {
                        "excitation_nm": row["excitation_nm"],
                        "emission_nm": row["emission_nm"],
                    }
                )
        else:
            subset = grid_f.loc[sel_f_idxs].reset_index(drop=True)
            st.write("Summary for selected fluors:")
            st.dataframe(
                subset[
                    [
                        "code",
                        "nickname",
                        "display_name",
                        "excitation_nm",
                        "emission_nm",
                    ]
                ],
                width="stretch",
            )

        st.download_button(
            "⬇︎ Download fluors (CSV)",
            data=df_f.to_csv(index=False).encode("utf-8"),
            file_name="fluors_overview_v11.csv",
            type="secondary",
            mime="text/csv",
        )

# ════════════════════════════════════════════════════════
# TAB 4 — TAGS
# ════════════════════════════════════════════════════════
with tab_tags:
    st.subheader("Tags")

    with st.form("tag_filters_cf", clear_on_submit=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            q_raw_t = st.text_input(
                "Search (code / nickname / display_name / localization / notes)",
                "",
                key="tags_cf_search",
            )
        with c2:
            lim_t = int(
                st.number_input(
                    "Limit (tags)",
                    min_value=50,
                    max_value=5000,
                    value=1000,
                    step=50,
                    key="tags_cf_limit",
                )
            )
        _ = st.form_submit_button("Apply", key="tags_cf_apply")

    def _normalize_tag(s: str | None) -> Optional[str]:
        s = (s or "").strip()
        return s or None

    q_t = _normalize_tag(q_raw_t)
    q_t_param = q_t or None

    sql_tags = text(
        """
        SELECT
          id::text           AS id,
          code               AS code,
          COALESCE(nickname,'')     AS nickname,
          COALESCE(display_name,'') AS display_name,
          localization,
          notes,
          created_at
        FROM public.tags
        WHERE (
             :q IS NULL
          OR  code                      ILIKE :ql
          OR  COALESCE(nickname,'')     ILIKE :ql
          OR  COALESCE(display_name,'') ILIKE :ql
          OR  COALESCE(localization,'') ILIKE :ql
          OR  COALESCE(notes,'')        ILIKE :ql
        )
        ORDER BY display_name, code
        LIMIT :limit;
        """
    )

    params_t = {
        "q": q_t_param,
        "ql": f"%{q_t}%" if q_t else None,
        "limit": lim_t,
    }

    with _eng().begin() as cx:
        df_t = pd.read_sql(sql_tags, cx, params=params_t)

    df_t = df_t.fillna("")
    st.caption(f"{len(df_t)} tag(s)")

    view_t = pd.DataFrame(
        {
            "code": df_t["code"],
            "nickname": df_t["nickname"],
            "display_name": df_t["display_name"],
            "type": ["tag"] * len(df_t),
            "localization": df_t["localization"],
            "notes": df_t["notes"],
            "created_at": df_t["created_at"],
            "id": df_t["id"],
        }
    )
    view_t.insert(0, "✓ Select", False)

    grid_t = st.data_editor(
        view_t,
        key="tags_overview_cf",
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        column_order=[
            "✓ Select",
            "code",
            "nickname",
            "display_name",
            "type",
            "localization",
            "notes",
            "created_at",
        ],
        column_config={
            "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
            "code": st.column_config.TextColumn("code (TAG-…)", disabled=True),
            "nickname": st.column_config.TextColumn("nickname", disabled=True),
            "display_name": st.column_config.TextColumn(
                "display_name", disabled=True
            ),
            "type": st.column_config.TextColumn("Type", disabled=True),
            "localization": st.column_config.TextColumn("Localization", disabled=True),
            "notes": st.column_config.TextColumn("Notes", disabled=True),
            "created_at": st.column_config.DatetimeColumn("Created", disabled=True),
            "id": st.column_config.TextColumn("ID", disabled=True),
        },
    )

    sel_t_ids: List[str] = []
    if isinstance(grid_t, pd.DataFrame) and "✓ Select" in grid_t.columns:
        sel_t_ids = grid_t.loc[grid_t["✓ Select"] == True, "id"].astype(str).tolist()

    st.divider()
    st.subheader("Tag details")

    if not sel_t_ids:
        st.info("Select one or more tags above to see details.")
    elif len(sel_t_ids) == 1:
        row = grid_t.loc[grid_t["id"].isin(sel_t_ids)].iloc[0]
        st.write(
            {
                "code": row["code"],
                "nickname": row["nickname"],
                "display_name": row["display_name"],
                "localization": row["localization"],
                "notes": row["notes"],
            }
        )
    else:
        subset = grid_t[grid_t["id"].isin(sel_t_ids)].reset_index(drop=True)
        st.write("Summary for selected tags:")
        st.dataframe(
            subset[
                [
                    "code",
                    "nickname",
                    "display_name",
                    "localization",
                ]
            ],
            width="stretch",
        )

    st.download_button(
        "⬇︎ Download tags (CSV)",
        data=df_t.to_csv(index=False).encode("utf-8"),
        file_name="tags_overview_v11.csv",
        type="secondary",
        mime="text/csv",
    )