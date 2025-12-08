# carp_app/ui/pages/215_🧪_add_treatments.py
from __future__ import annotations

import os
import sys
import uuid
import pathlib
from typing import Any, Dict, List, Optional, Tuple

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
from carp_app.ui.lib.page_engine import engine as _engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🧪 Add treatments (v11)",
    page_icon="🧪",
    layout="wide",
)
st.title("🧪 Add treatments (v11) — define treatment mixes from constructs & dyes")


def eng() -> Engine:
    return _engine()


def _norm(s: Optional[str]) -> str:
    s = (s or "").strip()
    return s


# ────────────────────────────────────────────────────────
# Verifier helpers (existing mixes, schema, etc.)
# ────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_existing_mixes() -> pd.DataFrame:
    """
    Load all existing treatment mixes with their construct (+delivery_form) and dye sets.
    """
    sql = text(
        """
        SELECT
          tm.id::text                  AS mix_id,
          tm.treatment_id::text        AS treatment_id,
          t.treat_code,
          t.kind_code,
          t.treat_text,
          COALESCE(t.nickname,'')      AS nickname,
          COALESCE(t.display_name,'')  AS display_name,
          ARRAY_AGG(DISTINCT tmc.construct_id::text || '|' || COALESCE(tmc.delivery_form,'')) 
            FILTER (WHERE tmc.construct_id IS NOT NULL)
            AS construct_pairs,
          ARRAY_AGG(DISTINCT tmd.dye_id::text)
            FILTER (WHERE tmd.dye_id IS NOT NULL)
            AS dye_ids
        FROM public.treatment_mixes tm
        JOIN public.treatments t
          ON t.id = tm.treatment_id
        LEFT JOIN public.treatment_mix_constructs tmc
          ON tmc.mix_id = tm.id
        LEFT JOIN public.treatment_mix_dyes tmd
          ON tmd.mix_id = tm.id
        GROUP BY
          tm.id,
          tm.treatment_id,
          t.treat_code,
          t.kind_code,
          t.treat_text,
          t.nickname,
          t.display_name
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)

    for col in ("construct_pairs", "dye_ids"):
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: list(v)
                if isinstance(v, (list, tuple))
                else ([] if pd.isna(v) else [str(v)])
            )
    return df


def find_existing_mix_for_ingredients(
    construct_ingredients: List[Tuple[str, Optional[str]]],
    dye_ids: List[str],
) -> Optional[Dict[str, Any]]:
    """
    Return an existing mix whose (construct_id,delivery_form) + dye_ids
    sets exactly match the given ingredients, or None.
    """
    target_pairs = {f"{cid}|{form or ''}" for cid, form in construct_ingredients}
    target_dyes = set(dye_ids)

    mixes_df = load_existing_mixes()
    if mixes_df.empty:
        return None

    for _, row in mixes_df.iterrows():
        row_pairs = set(row.get("construct_pairs") or [])
        row_dyes = set(row.get("dye_ids") or [])
        if row_pairs == target_pairs and row_dyes == target_dyes:
            return row.to_dict()

    return None


def _get_table_cols(table: str, schema: str = "public") -> List[str]:
    with eng().begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = :s
                  AND table_name   = :t
                ORDER BY ordinal_position;
                """
            ),
            cx,
            params={"s": schema, "t": table},
        )
    return df["column_name"].tolist()


# Cache these once per run
_TREATMENT_MIX_COLS: Optional[List[str]] = None
_TREATMENT_MIX_CONSTRUCT_COLS: Optional[List[str]] = None
_TREATMENT_MIX_DYE_COLS: Optional[List[str]] = None


def _ensure_mix_rows(
    cx,
    treatment_id: str,
    construct_ingredients: List[Tuple[str, Optional[str]]],
    dye_ids: List[str],
) -> None:
    """
    Create one treatment_mixes row for this treatment and attach
    construct + dye ingredients, using whatever columns actually
    exist on the mix tables.

    construct_ingredients: list of (construct_id, delivery_form)
      where delivery_form ∈ {'plasmid','rna','crispr'} or None.
    """
    global _TREATMENT_MIX_COLS, _TREATMENT_MIX_CONSTRUCT_COLS, _TREATMENT_MIX_DYE_COLS

    if _TREATMENT_MIX_COLS is None:
        _TREATMENT_MIX_COLS = _get_table_cols("treatment_mixes")
    if _TREATMENT_MIX_CONSTRUCT_COLS is None:
        _TREATMENT_MIX_CONSTRUCT_COLS = _get_table_cols("treatment_mix_constructs")
    if _TREATMENT_MIX_DYE_COLS is None:
        _TREATMENT_MIX_DYE_COLS = _get_table_cols("treatment_mix_dyes")

    mix_id = str(uuid.uuid4())

    mix_fields: List[str] = []
    mix_values: List[str] = []
    params: Dict[str, Any] = {}

    if "id" in _TREATMENT_MIX_COLS:
        mix_fields.append("id")
        mix_values.append(":mix_id")
        params["mix_id"] = mix_id

    if "treatment_id" in _TREATMENT_MIX_COLS:
        mix_fields.append("treatment_id")
        mix_values.append("CAST(:treatment_id AS uuid)")
        params["treatment_id"] = treatment_id

    if "mix_code" in _TREATMENT_MIX_COLS:
        mix_fields.append("mix_code")
        mix_values.append(":mix_code")
        params["mix_code"] = f"MIX-{mix_id[:8]}"

    if "created_at" in _TREATMENT_MIX_COLS:
        mix_fields.append("created_at")
        mix_values.append("now()")

    if "source_system" in _TREATMENT_MIX_COLS:
        mix_fields.append("source_system")
        mix_values.append("'add_treatments_ui'")
    if "import_batch_id" in _TREATMENT_MIX_COLS:
        mix_fields.append("import_batch_id")
        mix_values.append("'add_treatments_ui'")

    if mix_fields:
        sql = text(
            f"""
            INSERT INTO public.treatment_mixes (
              {", ".join(mix_fields)}
            )
            VALUES (
              {", ".join(mix_values)}
            );
            """
        )
        cx.execute(sql, params)

    # construct ingredients
    if construct_ingredients:
        for cid, delivery_form in construct_ingredients:
            fields: List[str] = []
            values: List[str] = []
            p: Dict[str, Any] = {}

            if "id" in _TREATMENT_MIX_CONSTRUCT_COLS:
                fields.append("id")
                values.append("gen_random_uuid()")

            if "mix_id" in _TREATMENT_MIX_CONSTRUCT_COLS:
                fields.append("mix_id")
                values.append("CAST(:mix_id AS uuid)")
                p["mix_id"] = mix_id

            if "construct_id" in _TREATMENT_MIX_CONSTRUCT_COLS:
                fields.append("construct_id")
                values.append("CAST(:cid AS uuid)")
                p["cid"] = cid

            if "delivery_form" in _TREATMENT_MIX_CONSTRUCT_COLS:
                fields.append("delivery_form")
                values.append(":delivery_form")
                p["delivery_form"] = delivery_form

            if "created_at" in _TREATMENT_MIX_CONSTRUCT_COLS:
                fields.append("created_at")
                values.append("now()")

            if not fields:
                continue

            sql = text(
                f"""
                INSERT INTO public.treatment_mix_constructs (
                  {", ".join(fields)}
                )
                VALUES (
                  {", ".join(values)}
                );
                """
            )
            cx.execute(sql, p)

    # dye ingredients
    if dye_ids:
        for did in dye_ids:
            fields: List[str] = []
            values: List[str] = []
            p2: Dict[str, Any] = {}

            if "id" in _TREATMENT_MIX_DYE_COLS:
                fields.append("id")
                values.append("gen_random_uuid()")

            if "mix_id" in _TREATMENT_MIX_DYE_COLS:
                fields.append("mix_id")
                values.append("CAST(:mix_id AS uuid)")
                p2["mix_id"] = mix_id

            if "dye_id" in _TREATMENT_MIX_DYE_COLS:
                fields.append("dye_id")
                values.append("CAST(:did AS uuid)")
                p2["did"] = did

            if "created_at" in _TREATMENT_MIX_DYE_COLS:
                fields.append("created_at")
                values.append("now()")

            if not fields:
                continue

            sql = text(
                f"""
                INSERT INTO public.treatment_mix_dyes (
                  {", ".join(fields)}
                )
                VALUES (
                  {", ".join(values)}
                );
                """
            )
            cx.execute(sql, p2)


def _create_treatment(
    treat_code: str,
    nickname: str,
    treat_text: str,
    kind_code: str,
    construct_ingredients: List[Tuple[str, Optional[str]]],
    dye_ids: List[str],
) -> str:
    """
    Insert a treatment plus its mix + ingredient rows.
    Returns treatment_id::text.
    """
    treat_code = _norm(treat_code)
    nickname = _norm(nickname)
    treat_text = _norm(treat_text)
    kind_code = _norm(kind_code) or "custom_mix"

    if not treat_code:
        raise ValueError("treat_code is required.")
    if not treat_text:
        treat_text = treat_code

    with eng().begin() as cx:
        row = cx.execute(
            text(
                """
                SELECT id::text AS treatment_id
                FROM public.treatments
                WHERE treat_code = :code
                LIMIT 1;
                """
            ),
            {"code": treat_code},
        ).fetchone()

        if row:
            treatment_id = row._mapping["treatment_id"]
            cx.execute(
                text(
                    """
                    UPDATE public.treatments
                    SET
                      kind_code    = COALESCE(:kind_code, kind_code),
                      treat_text   = COALESCE(:treat_text, treat_text),
                      nickname     = COALESCE(:nickname, nickname),
                      display_name = COALESCE(:display_name, display_name)
                    WHERE id = CAST(:tid AS uuid);
                    """
                ),
                {
                    "kind_code": kind_code,
                    "treat_text": treat_text,
                    "nickname": nickname or None,
                    "display_name": nickname or treat_text,
                    "tid": treatment_id,
                },
            )
        else:
            res = cx.execute(
                text(
                    """
                    INSERT INTO public.treatments (
                      id,
                      treat_code,
                      kind_code,
                      treat_text,
                      notes,
                      created_at,
                      source_system,
                      import_batch_id,
                      nickname,
                      display_name,
                      treatment_type
                    )
                    VALUES (
                      gen_random_uuid(),
                      :treat_code,
                      :kind_code,
                      :treat_text,
                      NULL,
                      now(),
                      'add_treatments_ui',
                      'add_treatments_ui',
                      :nickname,
                      :display_name,
                      'injection'
                    )
                    RETURNING id::text AS treatment_id;
                    """
                ),
                {
                    "treat_code": treat_code,
                    "kind_code": kind_code,
                    "treat_text": treat_text,
                    "nickname": nickname or None,
                    "display_name": nickname or treat_text,
                },
            ).fetchone()
            treatment_id = res._mapping["treatment_id"]

        if construct_ingredients or dye_ids:
            _ensure_mix_rows(cx, treatment_id, construct_ingredients, dye_ids)

    return treatment_id


# ────────────────────────────────────────────────────────
# Load choices (constructs + dyes)
# ────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_construct_choices(
    q: Optional[str],
    injection_mode: Optional[str],
    limit: int = 200,
) -> pd.DataFrame:
    """
    Load constructs for treatment definition.

    We join public.constructs (for id/base_code) to v_constructs_overview
    (for display fields + injection flags), keyed by construct_code.

    injection_mode:
      None        → no filter
      'plasmid'   → injection_use_plasmid IS TRUE
      'rna'       → injection_use_rna IS TRUE
      'crispr'    → injection_use_crispr IS TRUE
    """
    where: List[str] = ["1=1"]
    params: Dict[str, object] = {"lim": int(limit)}

    if q:
        params["ql"] = f"%{q}%"
        where.append(
            "("
            "  k.base_code ILIKE :ql"
            " OR k.construct_code ILIKE :ql"
            " OR COALESCE(c.construct_name,'') ILIKE :ql"
            " OR COALESCE(c.description,'') ILIKE :ql"
            ")"
        )

    if injection_mode == "plasmid":
        where.append("COALESCE(c.injection_use_plasmid, FALSE) IS TRUE")
    elif injection_mode == "rna":
        where.append("COALESCE(c.injection_use_rna, FALSE) IS TRUE")
    elif injection_mode == "crispr":
        where.append("COALESCE(c.injection_use_crispr, FALSE) IS TRUE")

    where_sql = " AND ".join(where)

    sql = text(
        f"""
        SELECT
          k.id::text                         AS construct_id,
          k.construct_code                   AS construct_code,
          COALESCE(c.construct_name,'')      AS construct_name,
          k.base_code                        AS base_code,
          COALESCE(c.fusion_pretty,'')       AS fusion_pretty,
          COALESCE(c.organelle_fluors,'')    AS organelle_fluors,
          COALESCE(c.injection_use_plasmid, FALSE) AS injection_use_plasmid,
          COALESCE(c.injection_use_rna,     FALSE) AS injection_use_rna,
          COALESCE(c.injection_use_crispr,  FALSE) AS injection_use_crispr
        FROM public.constructs k
        LEFT JOIN public.v_constructs_overview c
          ON c.construct_code = k.construct_code
        WHERE {where_sql}
        ORDER BY k.construct_code
        LIMIT :lim;
        """
    )

    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype("string").fillna("")

    def _kind(row: pd.Series) -> str:
        modes: List[str] = []
        if bool(row.get("injection_use_plasmid")):
            modes.append("plasmid")
        if bool(row.get("injection_use_rna")):
            modes.append("rna")
        if bool(row.get("injection_use_crispr")):
            modes.append("crispr")
        return " + ".join(modes)

    if not df.empty:
        df["injection_kind"] = df.apply(_kind, axis=1)

    return df


@st.cache_data(show_spinner=False)
def load_dye_choices(q: Optional[str]) -> pd.DataFrame:
    where = ["1=1"]
    params: Dict[str, Any] = {}
    if q:
        params["ql"] = f"%{q}%"
        where.append(
            "("
            "  d.code ILIKE :ql"
            " OR COALESCE(d.nickname,'') ILIKE :ql"
            " OR COALESCE(d.display_name,'') ILIKE :ql"
            " OR COALESCE(d.notes,'') ILIKE :ql"
            ")"
        )

    sql = text(
        f"""
        SELECT
          d.id::text        AS dye_id,
          d.code            AS base_code,
          COALESCE(d.display_name, d.nickname, d.code) AS display_name,
          COALESCE(d.notes,'') AS notes
        FROM public.dyes d
        WHERE {" AND ".join(where)}
        ORDER BY d.code, d.display_name;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype("string").fillna("")
    return df


# ────────────────────────────────────────────────────────
# STEP 1 — pick constructs & dyes
# ────────────────────────────────────────────────────────

st.subheader("Step 1 — Pick construct and dye ingredients", anchor=False)

c_search, d_search = st.columns(2)
with c_search:
    q_constructs = st.text_input(
        "Filter constructs (code / name / base code / description)",
        "",
        key="treat_construct_filter",
    )
with d_search:
    q_dyes = st.text_input(
        "Filter dyes (base code / name / notes)",
        "",
        key="treat_dye_filter",
    )

mode_label_to_key: Dict[str, Optional[str]] = {
    "All injection modes": None,
    "Plasmid-capable": "plasmid",
    "RNA-capable": "rna",
    "CRISPR-capable": "crispr",
}
mode_label = st.radio(
    "Injection capability filter (from v_constructs_overview)",
    options=list(mode_label_to_key.keys()),
    index=0,
    horizontal=True,
    key="treat_construct_injection_mode",
)
injection_mode_key = mode_label_to_key[mode_label]

constructs_df = load_construct_choices(_norm(q_constructs), injection_mode_key)
dyes_df = load_dye_choices(_norm(q_dyes))

# --- constructs table ---
construct_ingredients: List[Tuple[str, Optional[str]]] = []

if constructs_df.empty:
    st.info("No constructs found (check seeds / filters).")
else:
    st.caption("Constructs (plasmids / RNAs / CRISPR / other)")
    c_df = constructs_df.copy()
    c_df.insert(0, "Use CRISPR", False)
    c_df.insert(0, "Use RNA", False)
    c_df.insert(0, "Use plasmid", False)

    c_view = c_df[
        [
            "Use plasmid",
            "Use RNA",
            "Use CRISPR",
            "construct_code",
            "construct_name",
            "injection_kind",
            "base_code",
            "fusion_pretty",
            "organelle_fluors",
        ]
    ]

    c_pick = st.data_editor(
        c_view,
        key="treatment_construct_picker",
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        column_config={
            "Use plasmid": st.column_config.CheckboxColumn("plasmid", default=False),
            "Use RNA": st.column_config.CheckboxColumn("rna", default=False),
            "Use CRISPR": st.column_config.CheckboxColumn("crispr", default=False),
            "construct_code": st.column_config.TextColumn("Code", disabled=True),
            "construct_name": st.column_config.TextColumn(
                "Name", disabled=True, width="large"
            ),
            "injection_kind": st.column_config.TextColumn(
                "Injection capable (plasmid / rna / crispr)", disabled=True
            ),
            "base_code": st.column_config.TextColumn("Base code", disabled=True),
            "fusion_pretty": st.column_config.TextColumn(
                "Marker — fluor::tag(tag_pos)", disabled=True, width="large"
            ),
            "organelle_fluors": st.column_config.TextColumn(
                "Marker — organelle–fluor", disabled=True, width="large"
            ),
        },
    )

    for idx, row in c_pick.iterrows():
        cid = constructs_df.iloc[idx]["construct_id"]
        if row.get("Use plasmid"):
            construct_ingredients.append((cid, "plasmid"))
        if row.get("Use RNA"):
            construct_ingredients.append((cid, "rna"))
        if row.get("Use CRISPR"):
            construct_ingredients.append((cid, "crispr"))

# --- dyes table ---
if dyes_df.empty:
    st.caption("No dyes found.")
    selected_dye_ids: List[str] = []
else:
    st.caption("Dyes")
    d_df = dyes_df.copy()
    d_df.insert(0, "✓ Ingredient", False)

    d_view = d_df[
        [
            "✓ Ingredient",
            "base_code",
            "display_name",
            "notes",
        ]
    ]
    d_pick = st.data_editor(
        d_view,
        key="treatment_dye_picker",
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        column_config={
            "✓ Ingredient": st.column_config.CheckboxColumn("✓", default=False),
            "base_code": st.column_config.TextColumn("Dye base code", disabled=True),
            "display_name": st.column_config.TextColumn(
                "Name", disabled=True, width="large"
            ),
            "notes": st.column_config.TextColumn(
                "Notes", disabled=True, width="large"
            ),
        },
    )
    d_mask = (
        d_pick.get("✓ Ingredient", pd.Series(False, index=d_pick.index))
        .fillna(False)
        .astype(bool)
    )
    selected_dye_ids = (
        dyes_df.loc[d_mask, "dye_id"].astype(str).tolist()
        if d_mask.any()
        else []
    )

n_unique_constructs = len({cid for cid, _ in construct_ingredients})
st.caption(
    f"Selected ingredients: {n_unique_constructs} construct(s), "
    f"{len(selected_dye_ids)} dye(s)"
)

# ────────────────────────────────────────────────────────
# STEP 1b — marker preview
# ────────────────────────────────────────────────────────

st.markdown("### Marker preview (for selected ingredients)")

if not construct_ingredients and not selected_dye_ids:
    st.caption("Select constructs and/or dyes above to see a marker preview.")
else:
    sel_construct_ids = {cid for cid, _ in construct_ingredients}
    sel_constructs = (
        constructs_df[constructs_df["construct_id"].isin(sel_construct_ids)].copy()
        if not constructs_df.empty
        else pd.DataFrame()
    )
    sel_dyes = (
        dyes_df[dyes_df["dye_id"].isin(selected_dye_ids)].copy()
        if not dyes_df.empty
        else pd.DataFrame()
    )

    basecodes: List[str] = []
    if not sel_constructs.empty:
        basecodes.extend(sel_constructs["base_code"].astype(str).tolist())
    if not sel_dyes.empty:
        basecodes.extend(sel_dyes["base_code"].astype(str).tolist())
    basecodes = sorted({b for b in basecodes if b})

    fluor_tags: List[str] = []
    organelles: List[str] = []

    if "fusion_pretty" in sel_constructs.columns:
        for v in sel_constructs["fusion_pretty"]:
            if v and str(v).strip():
                fluor_tags.append(str(v).strip())
    if "organelle_fluors" in sel_constructs.columns:
        for v in sel_constructs["organelle_fluors"]:
            if v and str(v).strip():
                organelles.append(str(v).strip())

    fluor_tags = sorted({ft for ft in fluor_tags if ft})
    organelles = sorted({og for og in organelles if og})

    preview_df = pd.DataFrame(
        [
            {
                "genotype_basecode_code": ", ".join(basecodes),
                "fluor_tag_style": " + ".join(fluor_tags),
                "fluor_organelle_style": " + ".join(organelles),
            }
        ]
    )

    st.dataframe(
        preview_df,
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "This is a **preview**. After saving, "
        "v11_treatment_label_star will compute canonical label fields."
    )

# ────────────────────────────────────────────────────────
# STEP 2 — define treatment metadata
# ────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Step 2 — Define treatment metadata", anchor=False)

creator = (
    getattr(user, "email", None)
    or os.getenv("USER")
    or os.getenv("USERNAME")
    or "system"
)

with st.form("treatment_meta_form", clear_on_submit=False):
    m1, m2 = st.columns([2, 1])
    with m1:
        treat_code = st.text_input(
            "Treatment code (treat_code)",
            value="T-" + uuid.uuid4().hex[:6],
            help="Short code for this treatment (e.g. T-LEGACY-002, T-MIX-001).",
        )
        nickname = st.text_input(
            "Nickname (optional)",
            value="",
            help="Short human name for the treatment (used in labels).",
        )
        treat_text = st.text_area(
            "Treatment description",
            value="",
            height=80,
            help="Longer description; if empty, treat_code will be reused.",
        )
    with m2:
        kind_code = st.selectbox(
            "Kind",
            options=[
                "injection_single_base",
                "injection_mix",
                "dye_only",
                "custom_mix",
            ],
            index=1,
            help="Kind code for treatment_kinds; choose the closest match.",
        )

    submit_treatment = st.form_submit_button(
        "💾 Save treatment",
        type="primary",
        use_container_width=True,
    )

if submit_treatment:
    if not construct_ingredients and not selected_dye_ids:
        st.error("Select at least one construct or dye ingredient before saving a treatment.")
    else:
        existing_mix = find_existing_mix_for_ingredients(
            construct_ingredients,
            selected_dye_ids,
        )
        if existing_mix is not None:
            st.error(
                "A treatment with **exactly this ingredient mix** already exists. "
                "Please reuse that treatment code or change the ingredients."
            )
            mix_view = pd.DataFrame([existing_mix])[
                [
                    "treat_code",
                    "kind_code",
                    "treat_text",
                    "nickname",
                    "display_name",
                    "construct_pairs",
                    "dye_ids",
                ]
            ]
            st.caption("Existing treatment with the same mix:")
            st.dataframe(
                mix_view,
                hide_index=True,
                width="stretch",
            )
        else:
            with eng().begin() as cx:
                existing = pd.read_sql(
                    text(
                        """
                        SELECT
                          t.id::text      AS treatment_id,
                          t.treat_code,
                          t.kind_code,
                          t.treat_text,
                          COALESCE(t.nickname,'')      AS nickname,
                          COALESCE(t.display_name,'')  AS display_name
                        FROM public.treatments t
                        WHERE t.treat_code = :code
                        LIMIT 1;
                        """
                    ),
                    cx,
                    params={"code": treat_code.strip()},
                )

                if not existing.empty:
                    tid = existing.iloc[0]["treatment_id"]
                    try:
                        existing_labels = pd.read_sql(
                            text(
                                """
                                SELECT
                                  treat_code,
                                  kind_code,
                                  treat_text,
                                  genotype_basecode_code,
                                  fluor_tag_style,
                                  fluor_organelle_style
                                FROM public.v11_treatment_label_star
                                WHERE treatment_id = :tid
                                ORDER BY treat_code
                                """
                            ),
                            cx,
                            params={"tid": tid},
                        )
                    except Exception:
                        existing_labels = pd.DataFrame()
                else:
                    existing_labels = pd.DataFrame()

            if not existing.empty:
                st.error(
                    f"Treatment code **{treat_code}** already exists. "
                    "You must choose a new code if you want a different treatment."
                )
                st.caption("Existing treatment with this code:")
                st.dataframe(
                    existing,
                    hide_index=True,
                    width="stretch",
                )
                if not existing_labels.empty:
                    st.caption("Existing treatment contents / marker styles:")
                    st.dataframe(
                        existing_labels,
                        hide_index=True,
                        width="stretch",
                    )
            else:
                try:
                    tid = _create_treatment(
                        treat_code=treat_code,
                        nickname=nickname,
                        treat_text=treat_text,
                        kind_code=kind_code,
                        construct_ingredients=construct_ingredients,
                        dye_ids=selected_dye_ids,
                    )
                    st.success(f"Treatment {treat_code} saved (id={tid}).")
                    st.info(
                        "Label views (v11_treatment_label_star) will pick this up automatically. "
                        "You can now attach this treatment to clutches or treated fish."
                    )
                except Exception as e:
                    st.error(f"Failed to save treatment: {type(e).__name__}: {e}")