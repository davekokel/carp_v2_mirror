from __future__ import annotations
import os, sys, uuid, pathlib
from typing import List

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── repo root / imports ──────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine

# ── auth / engine ────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🧪 Add / edit treatments", page_icon="🧪", layout="wide")
st.title("🧪 Add / edit treatments")

_ENGINE: Engine | None = None
def eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        if not os.getenv("DB_URL"):
            st.error("DB_URL not set"); st.stop()
        _ENGINE = get_engine()
    return _ENGINE

def _sql_df(sql: str, **params) -> pd.DataFrame:
    with eng().begin() as cx:
        return pd.read_sql(text(sql), cx, params=params)

def _view_exists(name: str) -> bool:
    sql = """
      SELECT 1
      FROM information_schema.views
      WHERE table_schema='public' AND table_name=:n
      UNION ALL
      SELECT 1
      FROM pg_catalog.pg_matviews
      WHERE schemaname='public' AND matviewname=:n
      LIMIT 1
    """
    with eng().begin() as cx:
        df = pd.read_sql(text(sql), cx, params={"n": name})
    return not df.empty

HAS_V11_TREATMENT_STAR = _view_exists("v11_treatment_star")
HAS_V11_CLUTCH_STAR    = _view_exists("v11_clutch_star")
TREATMENT_STAR_VIEW    = "public.v11_treatment_star"
CLUTCH_STAR_VIEW       = "public.v11_clutch_star"

if not HAS_V11_TREATMENT_STAR:
    st.error("public.v11_treatment_star is missing; please apply that migration first.")
    st.stop()

# ── helpers ──────────────────────────────────────────────────────────────────

def new_treat_code() -> str:
    return "TREAT-" + uuid.uuid4().hex[:8].upper()

def load_treatments_star(search: str) -> pd.DataFrame:
    s = (search or "").strip()
    where = []
    params = {}
    if s:
        where.append(
            "("
            "COALESCE(treatment_code,'')             ILIKE :q OR "
            "COALESCE(treat_text,'')                ILIKE :q OR "
            "COALESCE(genotype_basecode_code,'')    ILIKE :q OR "
            "COALESCE(all_fluor_tag_rollup,'')      ILIKE :q OR "
            "COALESCE(all_organelle_fluor_rollup,'') ILIKE :q"
            ")"
        )
        params["q"] = f"%{s}%"
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    return _sql_df(
        f"""
        SELECT *
        FROM {TREATMENT_STAR_VIEW}
        {where_sql}
        ORDER BY created_at DESC NULLS LAST, treatment_code
        LIMIT 500
        """,
        **params,
    )

def load_constructs(kind: str, search: str) -> pd.DataFrame:
    where = ["construct_kind = :k"]
    params = {"k": kind}
    s = (search or "").strip()
    if s:
        where.append(
            "("
            "COALESCE(construct_code,'') ILIKE :q OR "
            "COALESCE(construct_name,'') ILIKE :q OR "
            "COALESCE(nickname,'')      ILIKE :q OR "
            "COALESCE(description,'')   ILIKE :q"
            ")"
        )
        params["q"] = f"%{s}%"
    where_sql = "WHERE " + " AND ".join(where)
    return _sql_df(
        f"""
        SELECT
          id::text AS construct_id,
          construct_code,
          construct_kind,
          COALESCE(construct_name, construct_code) AS construct_name,
          created_at
        FROM public.constructs
        {where_sql}
        ORDER BY created_at DESC NULLS LAST, construct_code
        LIMIT 1000
        """,
        **params,
    )

def load_dyes(search: str) -> pd.DataFrame:
    where = []
    params = {}
    s = (search or "").strip()
    if s:
        where.append(
            "("
            "COALESCE(dye_base_code,'') ILIKE :q OR "
            "COALESCE(name,'')         ILIKE :q OR "
            "COALESCE(notes,'')        ILIKE :q"
            ")"
        )
        params["q"] = f"%{s}%"
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    return _sql_df(
        f"""
        SELECT
          id::text AS dye_id,
          dye_base_code AS dye_code,
          name,
          created_at
        FROM public.dyes
        {where_sql}
        ORDER BY created_at DESC NULLS LAST, dye_base_code
        LIMIT 1000
        """,
        **params,
    )

def load_existing_mix(treatment_id: str):
    mix = _sql_df(
        """
        SELECT id::text AS mix_id
        FROM public.treatment_mixes
        WHERE treatment_id = CAST(:tid AS uuid)
        LIMIT 1
        """,
        tid=treatment_id,
    )
    if mix.empty:
        empty = pd.DataFrame(columns=["material_type","material_code","material_name"])
        return None, [], [], empty

    mix_id = mix["mix_id"].iloc[0]
    cons = _sql_df(
        """
        SELECT
          c.id::text          AS construct_id,
          c.construct_kind    AS material_type,
          c.construct_code    AS material_code,
          COALESCE(c.construct_name,c.construct_code) AS material_name
        FROM public.treatment_mix_constructs tmc
        JOIN public.constructs c ON c.id = tmc.construct_id
        WHERE tmc.mix_id = CAST(:mid AS uuid)
        ORDER BY c.construct_code
        """,
        mid=mix_id,
    )
    dyes = _sql_df(
        """
        SELECT
          d.id::text          AS dye_id,
          'dye'               AS material_type,
          d.dye_base_code     AS material_code,
          d.name              AS material_name
        FROM public.treatment_mix_dyes tmd
        JOIN public.dyes d ON d.id = tmd.dye_id
        WHERE tmd.mix_id = CAST(:mid AS uuid)
        ORDER BY d.dye_base_code
        """,
        mid=mix_id,
    )

    existing_construct_ids = cons["construct_id"].tolist() if not cons.empty else []
    existing_dye_ids       = dyes["dye_id"].tolist() if not dyes.empty else []

    existing = pd.concat(
        [
            cons[["material_type","material_code","material_name"]],
            dyes[["material_type","material_code","material_name"]],
        ],
        ignore_index=True,
    ) if (not cons.empty or not dyes.empty) else pd.DataFrame(
        columns=["material_type","material_code","material_name"]
    )

    return mix_id, existing_construct_ids, existing_dye_ids, existing

def upsert_treatment(kind_code: str, treat_code: str, treat_text: str) -> str:
    with eng().begin() as cx:
        existing = pd.read_sql(
            text("SELECT id::text AS id FROM public.treatments WHERE treat_code=:c LIMIT 1"),
            cx,
            params={"c": treat_code},
        )
        if not existing.empty:
            tid = existing["id"].iloc[0]
            cx.execute(
                text(
                    "UPDATE public.treatments "
                    "SET kind_code=:k, treat_text=NULLIF(:t,'') "
                    "WHERE id=CAST(:id AS uuid)"
                ),
                {"k": kind_code, "t": treat_text, "id": tid},
            )
            return tid

        row = pd.read_sql(
            text(
                """
                INSERT INTO public.treatments
                  (id, kind_code, treat_code, treat_text, created_at)
                VALUES (gen_random_uuid(), :k, :c, NULLIF(:t,''), now())
                RETURNING id::text AS id
                """
            ),
            cx,
            params={"k": kind_code, "c": treat_code, "t": treat_text},
        )
        return row["id"].iloc[0]

def get_or_create_mix(treatment_id: str, treat_code: str) -> str:
    with eng().begin() as cx:
        existing = pd.read_sql(
            text(
                "SELECT id::text AS id FROM public.treatment_mixes "
                "WHERE treatment_id=CAST(:tid AS uuid) LIMIT 1"
            ),
            cx,
            params={"tid": treatment_id},
        )
        if not existing.empty:
            return existing["id"].iloc[0]

        row = pd.read_sql(
            text(
                """
                INSERT INTO public.treatment_mixes
                  (id, treatment_id, mix_code, created_at)
                VALUES (gen_random_uuid(), CAST(:tid AS uuid), :code, now())
                RETURNING id::text AS id
                """
            ),
            cx,
            params={"tid": treatment_id, "code": treat_code},
        )
        return row["id"].iloc[0]

def replace_mix_members(mix_id: str, construct_ids: List[str], dye_ids: List[str]):
    with eng().begin() as cx:
        cx.execute(
            text("DELETE FROM public.treatment_mix_constructs WHERE mix_id=CAST(:m AS uuid)"),
            {"m": mix_id},
        )
        cx.execute(
            text("DELETE FROM public.treatment_mix_dyes WHERE mix_id=CAST(:m AS uuid)"),
            {"m": mix_id},
        )
        for cid in construct_ids:
            cx.execute(
                text(
                    """
                    INSERT INTO public.treatment_mix_constructs
                      (id, mix_id, construct_id, created_at)
                    VALUES (gen_random_uuid(), CAST(:m AS uuid), CAST(:c AS uuid), now())
                    """
                ),
                {"m": mix_id, "c": cid},
            )
        for did in dye_ids:
            cx.execute(
                text(
                    """
                    INSERT INTO public.treatment_mix_dyes
                      (id, mix_id, dye_id, created_at)
                    VALUES (gen_random_uuid(), CAST(:m AS uuid), CAST(:d AS uuid), now())
                    """
                ),
                {"m": mix_id, "d": did},
            )

def infer_kind(df: pd.DataFrame, existing_kind: str | None) -> str:
    if existing_kind:
        return existing_kind
    if df.empty:
        return "mix"
    kinds = sorted(set(df["material_type"].astype(str)))
    return kinds[0] if len(kinds) == 1 else "mix"

# ── 0. existing treatments (from v11_treatment_star) ------------------------

st.subheader("0. Existing treatments")

c0a, _ = st.columns([2, 1])
with c0a:
    search_tx = st.text_input("Search (code / text / fluor / organelle)", key="tx_search")

tx_df = load_treatments_star(search_tx)

selected_row = None
selected_code = None
selected_kind = None

if tx_df.empty:
    st.caption("No treatments yet — selecting components below will create a new one.")
else:
    display_cols = [
        "treatment_code",
        "genotype_basecode_code",
        "genotype_transgene_allele_code",
        "all_fluor_tag_rollup",
        "all_organelle_fluor_rollup",
        "kind_code",
        "treat_text",
        "created_at",
    ]
    display_cols = [c for c in display_cols if c in tx_df.columns] + [
        c for c in tx_df.columns if c not in display_cols and c != "treatment_id"
    ]

    df_display = tx_df.copy()[["treatment_id"] + display_cols]
    df_display.insert(0, "✓", False)

    last_id = st.session_state.get("selected_treatment_id")
    if last_id:
        df_display.loc[df_display["treatment_id"] == last_id, "✓"] = True

    picker = st.data_editor(
        df_display.drop(columns=["treatment_id"]),
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False),
            "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
        },
        key="treatment_picker",
    )

    sel = picker.get("✓", pd.Series(False, index=picker.index)).fillna(False).astype(bool)
    selected = tx_df.loc[sel, :].reset_index(drop=True)

    if not selected.empty:
        selected_row  = selected.iloc[0]
        selected_code = selected_row["treatment_code"]
        selected_kind = selected_row["kind_code"]
        st.session_state["selected_treatment_id"] = selected_row["treatment_id"]
        st.caption(f"Extending existing treatment: {selected_code}")
    else:
        st.session_state.pop("selected_treatment_id", None)
        st.caption("No treatment selected — will create a new one.")

# ── existing mix for selection ----------------------------------------------

existing_components = pd.DataFrame(columns=["material_type","material_code","material_name"])
existing_construct_ids: List[str] = []
existing_dye_ids: List[str] = []

if selected_row is not None:
    _, existing_construct_ids, existing_dye_ids, existing_components = load_existing_mix(
        selected_row["treatment_id"]
    )

# ── 1. description -----------------------------------------------------------

st.subheader("1. Treatment description")

if "treat_text" not in st.session_state:
    st.session_state["treat_text"] = selected_row["treat_text"] if selected_row is not None else ""

if selected_row is not None and st.session_state.get("treat_text_loaded_for") != selected_row["treatment_id"]:
    st.session_state["treat_text"] = selected_row["treat_text"] or ""
    st.session_state["treat_text_loaded_for"] = selected_row["treatment_id"]

treat_text = st.text_input(
    "Description",
    key="treat_text",
    placeholder="e.g. pDQM series + dye for Korra imaging",
)

# ── 2. pick additional components -------------------------------------------

st.subheader("2. Pick additional components")

tabs = st.tabs(["Plasmids", "RNAs", "CRISPR", "Dyes"])

def construct_tab(tab_idx: int, kind: str, key_prefix: str) -> pd.DataFrame:
    with tabs[tab_idx]:
        q = st.text_input(f"Search {kind} constructs", key=f"{key_prefix}_q")
        df = load_constructs(kind, q)
        st.caption(f"{len(df)} {kind} construct(s)")
        if df.empty:
            return pd.DataFrame()
        df = df.copy()
        if "✓" not in df.columns:
            df.insert(0, "✓", False)
        edited = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "✓": st.column_config.CheckboxColumn("✓", default=False),
                "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
            },
            key=f"{key_prefix}_editor",
        )
        sel = edited.get("✓", pd.Series(False, index=edited.index)).fillna(False).astype(bool)
        picked = edited.loc[sel, :].reset_index(drop=True)
        st.caption(f"Selected {kind}: {len(picked)}")
        if picked.empty:
            return picked
        return picked.assign(
            material_type=kind,
            material_code=picked["construct_code"].astype(str),
            material_name=picked["construct_name"].astype(str),
        )

picked_plasmids = construct_tab(0, "plasmid", "plasmids")
picked_rnas     = construct_tab(1, "rna",     "rnas")
picked_crisprs  = construct_tab(2, "crispr",  "crisprs")

with tabs[3]:
    qd = st.text_input("Search dyes (base_code / name / notes)", key="dyes_q")
    dyes_df = load_dyes(qd)
    st.caption(f"{len(dyes_df)} dye(s)")
    if dyes_df.empty:
        picked_dyes = pd.DataFrame()
    else:
        dyes_df = dyes_df.copy()
        if "✓" not in dyes_df.columns:
            dyes_df.insert(0, "✓", False)
        edited = st.data_editor(
            dyes_df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "✓": st.column_config.CheckboxColumn("✓", default=False),
                "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
            },
            key="dyes_editor",
        )
        sel = edited.get("✓", pd.Series(False, index=edited.index)).fillna(False).astype(bool)
        picked_dyes = edited.loc[sel, :].reset_index(drop=True)
        st.caption(f"Selected dyes: {len(picked_dyes)}")
        if not picked_dyes.empty:
            picked_dyes = picked_dyes.assign(
                material_type="dye",
                material_code=picked_dyes["dye_code"].astype(str),
                material_name=picked_dyes["name"].astype(str),
            )

# ── 3. preview mix -----------------------------------------------------------

st.subheader("3. Preview mix components")

frames = [existing_components]
for df in [picked_plasmids, picked_rnas, picked_crisprs, picked_dyes]:
    if isinstance(df, pd.DataFrame) and not df.empty:
        frames.append(df[["material_type","material_code","material_name"]])

if frames:
    mix_df = pd.concat(frames, ignore_index=True)
    mix_df = mix_df.drop_duplicates(subset=["material_type","material_code"]).reset_index(drop=True)
else:
    mix_df = pd.DataFrame(columns=["material_type","material_code","material_name"])

st.caption(f"{len(mix_df)} component(s) in resulting mix")
if mix_df.empty:
    st.info("No components yet — select an existing treatment or add constructs/dyes above.")
else:
    st.data_editor(
        mix_df,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=True,
        key="preview_mix",
    )

kind_effective = infer_kind(mix_df, selected_kind)
code_effective = selected_code or new_treat_code()
if selected_code:
    st.caption(f"Extending existing treatment **{code_effective}** (kind={kind_effective})")
else:
    st.caption(f"Creating new treatment **{code_effective}** (kind={kind_effective})")

# ── 4. save ------------------------------------------------------------------

st.subheader("4. Save treatment + mix")

if st.button("💾 Save treatment", use_container_width=True):
    if mix_df.empty:
        st.error("Mix is empty; add at least one component before saving.")
    else:
        construct_ids: List[str] = list(existing_construct_ids)
        dye_ids:       List[str] = list(existing_dye_ids)

        for df in [picked_plasmids, picked_rnas, picked_crisprs]:
            if isinstance(df, pd.DataFrame) and not df.empty:
                construct_ids.extend(df["construct_id"].astype(str).tolist())
        if isinstance(picked_dyes, pd.DataFrame) and not picked_dyes.empty:
            dye_ids.extend(picked_dyes["dye_id"].astype(str).tolist())

        construct_ids = sorted(set(construct_ids))
        dye_ids       = sorted(set(dye_ids))

        if not construct_ids and not dye_ids:
            st.error("Selection did not resolve to any construct_id or dye_id.")
        else:
            try:
                tid = upsert_treatment(kind_effective, code_effective, treat_text.strip())
                mid = get_or_create_mix(tid, code_effective)
                replace_mix_members(mid, construct_ids, dye_ids)
                st.success(
                    f"Saved treatment {code_effective} (kind={kind_effective}) "
                    f"with {len(construct_ids)} construct(s) and {len(dye_ids)} dye(s)."
                )
                st.session_state["last_saved_treat_code"] = code_effective
            except Exception as e:
                st.error(f"Error saving treatment: {e}")

# ── 5. where used (v11_clutch_star) -----------------------------------------

st.subheader("5. Where this treatment is used (v11_clutch_star)")

if not HAS_V11_CLUTCH_STAR:
    st.info("v11_clutch_star not available; cannot show rollup.")
else:
    preview_code = (
        st.session_state.get("last_saved_treat_code")
        or selected_code
        or ""
    )
    if not preview_code:
        st.info("Save or select a treatment above to see where it is used.")
    else:
        df_roll = _sql_df(
            f"""
            SELECT *
            FROM {CLUTCH_STAR_VIEW}
            WHERE treatment_code = :c
            ORDER BY clutch_date DESC NULLS LAST
            LIMIT 100
            """,
            c=preview_code,
        )
        st.caption(f"{len(df_roll)} clutch(es) with treatment_code = {preview_code}")
        if df_roll.empty:
            st.info("No clutches currently use this treatment.")
        else:
            cols_pref = [
                "clutch_id",
                "clutch_code",
                "clutch_date",
                "genotype_basecode_code",
                "genotype_transgene_allele_code",
                "treatment_code",
                "treatments_and_transgenes",
                "all_fluor_tag_rollup",
                "all_organelle_fluor_rollup",
            ]
            cols = [c for c in cols_pref if c in df_roll.columns] or df_roll.columns.tolist()
            st.data_editor(
                df_roll[cols],
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                disabled=True,
                key="rollup_preview",
            )