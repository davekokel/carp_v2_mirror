# carp_app/ui/pages/200_🧪_add_treatments_to_clutch.py

from __future__ import annotations
import sys, pathlib, os
from datetime import date, timedelta
from typing import List, Dict, Any, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root on sys.path
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

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🧪 Add treatments to clutch", page_icon="🧪", layout="wide")
st.title("🧪 Add treatments to clutch")

# ── Engine ───────────────────────────────────────────────────────────────────
_ENGINE: Engine | None = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        url = os.getenv("DB_URL")
        if not url:
            st.error("DB_URL not set"); st.stop()
        _ENGINE = get_engine()
    return _ENGINE

CLUTCHES_VIEW        = "public.v11_clutch_star"
FISH_STAR_VIEW       = "public.v11_fish_instance_star"
TREATMENT_STAR_VIEW  = "public.v11_treatment_star"

# ── Guards / helpers ---------------------------------------------------------


def _table_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        n = pd.read_sql(
            text("""
              SELECT count(*)::int AS n
              FROM information_schema.tables
              WHERE table_schema=:s AND table_name=:n
            """),
            cx,
            params={"s": schema, "n": name},
        )["n"][0]
    return n > 0


def _view_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        row = pd.read_sql(
            text("""
              SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n
              UNION ALL
              SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n
              LIMIT 1
            """),
            cx,
            params={"s": schema, "n": name},
        )
    return not row.empty


# required views/tables
if not _view_exists("public", "v11_clutch_star"):
    st.error("public.v11_clutch_star is missing; please apply that migration first.")
    st.stop()
if not _view_exists("public", "v11_fish_instance_star"):
    st.error("public.v11_fish_instance_star is missing; please apply that migration first.")
    st.stop()
if not _view_exists("public", "v11_treatment_star"):
    st.error("public.v11_treatment_star is missing; please apply that migration first.")
    st.stop()

for tname in ["clutches", "crosses", "join_clutch_treatments", "treatments"]:
    if not _table_exists("public", tname):
        st.error(f"Required table public.{tname} not found.")
        st.stop()

# ── Data loaders / utils -----------------------------------------------------


def _load_clutches(d_from, d_to, q: str, most_recent: bool) -> pd.DataFrame:
    """
    Pull clutches from v11_clutch_star and keep enough context for the picker.
    Filters out legacy clutches (LCL-* prefix).
    """
    with _eng().begin() as cx:
        df = pd.read_sql(text(f"SELECT * FROM {CLUTCHES_VIEW}"), cx)

    if df.empty:
        return df

    # normalize clutch_id
    if "clutch_id" in df.columns:
        df["clutch_id"] = df["clutch_id"].astype(str)
    elif "id" in df.columns:
        df["clutch_id"] = df["id"].astype(str)
    else:
        st.error(f"{CLUTCHES_VIEW} is missing clutch_id/id column.")
        st.stop()

    # filter legacy clutches: exclude LCL-*, keep everything else (modern)
    if "clutch_code" in df.columns:
        df["clutch_code"] = df["clutch_code"].astype(str)
        df = df[~df["clutch_code"].str.startswith("LCL-")]

    if df.empty:
        return df

    # clutch birthday/date
    birthday_col = None
    for cand in ["clutch_birthday", "clutch_date", "birthday", "date"]:
        if cand in df.columns:
            birthday_col = cand
            break
    if birthday_col is not None:
        df[birthday_col] = pd.to_datetime(df[birthday_col], errors="coerce").dt.date
        if not most_recent:
            mask = (df[birthday_col] >= d_from) & (df[birthday_col] <= d_to)
            df = df[mask]

    # search
    qnorm = (q or "").strip()
    if qnorm:
        qlow = qnorm.lower()
        search_cols = [
            c
            for c in [
                "clutch_code",
                "cross_run_code",
                "cross_code",
                "tank_pair_code",
                "genotype_basecode_code",
                "genotype_transgene_allele_code",
                "treatment_code",
                "treat_codes",
                "all_fluor_tag_rollup",
                "all_organelle_fluor_rollup",
            ]
            if c in df.columns
        ]
        if search_cols:
            mask = pd.Series(False, index=df.index)
            for c in search_cols:
                mask |= df[c].astype(str).str.lower().str.contains(qlow, na=False)
            df = df[mask]

    # sort
    sort_cols = [c for c in ["clutch_date", "clutch_created_at", "created_at"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=False)
    df = df.head(1000)

    # derived fields
    if birthday_col is None:
        df["clutch_birthday"] = pd.NaT
    else:
        if birthday_col != "clutch_birthday":
            df["clutch_birthday"] = df[birthday_col]

    if "cross_run_code" in df.columns:
        df["cross_name_pretty"] = df["cross_run_code"]
    elif "cross_code" in df.columns:
        df["cross_name_pretty"] = df["cross_code"]
    else:
        df["cross_name_pretty"] = ""

    # treatments_count_effective: does this clutch have any treatments?
    if "treatment_code" in df.columns:
        df["treatments_count_effective"] = (
            df["treatment_code"].fillna("").astype(str).ne("").astype(int)
        )
    elif "treat_codes" in df.columns:
        df["treatments_count_effective"] = (
            df["treat_codes"].fillna("").astype(str).ne("").astype(int)
        )
    else:
        df["treatments_count_effective"] = 0

    ui_cols = [
        "clutch_id",
        "clutch_code",
        "clutch_birthday",
        "clutch_date",
        "estimated_egg_count",
        "cross_name_pretty",
        "genotype_pretty",
        "genotype_basecode_code",
        "genotype_transgene_allele_code",
        "treatment_code",
        "treat_codes",
        "treatments_and_transgenes",
        "all_fluor_tag_rollup",
        "all_organelle_fluor_rollup",
        "tank_pair_code",
    ]
    for c in ui_cols:
        if c not in df.columns:
            df[c] = None
    return df[ui_cols]


def _load_treatments(kind_filter: str, search: str) -> pd.DataFrame:
    """
    Load treatments using standard treatment fields from v11_treatment_star.
    Assumes v11_treatment_star has materials_by_kind (plasmid/rna/crispr breakdown).
    """
    s = (search or "").strip()
    k = (kind_filter or "").strip()

    where = []
    params: Dict[str, Any] = {}
    if k:
        where.append("kind_code = :k")
        params["k"] = k
    if s:
        where.append(
            "(COALESCE(treatment_code,'') ILIKE :q OR COALESCE(treat_text,'') ILIKE :q)"
        )
        params["q"] = f"%{s}%"

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    sql = text(f"""
      SELECT
        treatment_id,
        treatment_code,
        genotype_basecode_code,
        COALESCE(materials_by_kind,'') AS materials_by_kind,
        all_fluor_tag_rollup,
        all_organelle_fluor_rollup,
        kind_code,
        treat_text,
        created_at
      FROM {TREATMENT_STAR_VIEW}
      {where_sql}
      ORDER BY created_at DESC NULLS LAST, treatment_code
      LIMIT 500
    """)

    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params=params)


def _load_clutch_treatments(clutch_id: str) -> pd.DataFrame:
    """
    Existing treatments attached to this clutch.
    Joins through v11_treatment_star so we see standard treatment fields.
    """
    sql = text(f"""
      SELECT
        jct.created_at,
        ts.treatment_code,
        ts.genotype_basecode_code,
        ts.materials_by_kind,
        ts.all_fluor_tag_rollup,
        ts.all_organelle_fluor_rollup,
        ts.kind_code,
        ts.treat_text
      FROM public.join_clutch_treatments jct
      JOIN {TREATMENT_STAR_VIEW} ts
        ON ts.treatment_id = jct.treatment_id::text
      WHERE jct.clutch_id = CAST(:cid AS uuid)
      ORDER BY jct.created_at DESC NULLS LAST
    """)
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params={"cid": clutch_id})


def _attach_treatments(
    clutch_id: str,
    created_by: str,  # kept for API symmetry, not stored
    treatment_ids: List[str],
) -> tuple[int, List[str]]:
    """
    Link existing treatments to this clutch via join_clutch_treatments.
    """
    inserted, errs = 0, []
    if not treatment_ids:
        return 0, []

    with _eng().begin() as cx:
        for tid in treatment_ids:
            tid = str(tid).strip()
            if not tid:
                continue
            exists = pd.read_sql(
                text("""
                  SELECT 1
                  FROM public.join_clutch_treatments
                  WHERE clutch_id = CAST(:cid AS uuid)
                    AND treatment_id = CAST(:tid AS uuid)
                  LIMIT 1
                """),
                cx,
                params={"cid": clutch_id, "tid": tid},
            )
            if not exists.empty:
                continue
            try:
                cx.execute(
                    text("""
                      INSERT INTO public.join_clutch_treatments
                        (id, clutch_id, treatment_id, applied_at, created_at)
                      VALUES
                        (gen_random_uuid(), CAST(:cid AS uuid), CAST(:tid AS uuid), now(), now())
                    """),
                    {"cid": clutch_id, "tid": tid},
                )
                inserted += 1
            except Exception as e:
                errs.append(str(e))
    return inserted, errs


def _load_parents_for_clutch(clutch_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Resolve mother and father fish from clutches.cross_id → crosses.[female|male]_fish_id
    then pull standard fields from v11_fish_instance_star.
    """
    clutch_id = (clutch_id or "").strip()
    if not clutch_id:
        return {}, {}

    with _eng().begin() as cx:
        # get female/male fish_instance_ids
        cross_row = pd.read_sql(
            text("""
              SELECT
                x.female_fish_id::text AS mom_fish_instance_id,
                x.male_fish_id::text   AS dad_fish_instance_id
              FROM public.clutches c
              JOIN public.crosses x ON x.id = c.cross_id
              WHERE c.id = CAST(:cid AS uuid)
              LIMIT 1
            """),
            cx,
            params={"cid": clutch_id},
        )
        if cross_row.empty:
            return {}, {}

        mom_fiid = cross_row["mom_fish_instance_id"].iloc[0]
        dad_fiid = cross_row["dad_fish_instance_id"].iloc[0]

        def _one(fid: str) -> Dict[str, Any]:
            fid = (fid or "").strip()
            if not fid:
                return {}
            df = pd.read_sql(
                text(f"""
                  SELECT *
                  FROM {FISH_STAR_VIEW}
                  WHERE fish_instance_id = CAST(:fid AS uuid)
                  ORDER BY fish_created_at DESC NULLS LAST
                  LIMIT 1
                """),
                cx,
                params={"fid": fid},
            )
            if df.empty:
                return {}
            return df.iloc[0].to_dict()

        mom = _one(mom_fiid)
        dad = _one(dad_fiid)

    return mom, dad


def _pivot(title: str, rows: List[Tuple[str, Any]]):
    dfp = pd.DataFrame(rows, columns=["Field", "Value"])
    st.markdown(f"**{title}**")
    st.dataframe(dfp, hide_index=True, use_container_width=True)

# ── 1. Selected clutch -------------------------------------------------------

st.subheader("1. Selected clutch")

with st.form("filters_form", clear_on_submit=False):
    today = date.today()
    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2:
        d2 = st.date_input("To", value=today + timedelta(days=14))
    with c3:
        qtxt = st.text_input("Search clutches (code/cross/genotype)", value="")
    r1, _ = st.columns([1, 3])
    with r1:
        ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    st.form_submit_button("Apply", use_container_width=True)

clutches = _load_clutches(d1, d2, qtxt, ignore_dates)
st.caption(f"{len(clutches)} modern clutch(es) (legacy LCL-* filtered out)")

if clutches.empty:
    st.info("No modern clutches found with the current filters.")
    st.stop()

dfv = clutches.copy()
dfv.insert(0, "✓ Select", False)
last_id = st.session_state.get("last_clutch_id")
if last_id:
    dfv.loc[dfv["clutch_id"] == last_id, "✓ Select"] = True

picker = st.data_editor(
    dfv,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("Clutch birthday", disabled=True, format="YYYY-MM-DD"),
        "treatments_count_effective": st.column_config.NumberColumn(
            "# treatments", format="%d"
        ),
    },
    key="clutch_picker_v11",
)

sel_mask = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False).astype(bool)
picked = dfv.loc[sel_mask, :].reset_index(drop=True)

if picked.empty:
    st.info("Select a clutch row, then choose treatments below.")
    st.stop()

row = picked.iloc[0]
clutch_id = str(row.get("clutch_id", "") or "").strip()
if not clutch_id:
    st.error("Selected row is missing clutch_id; cannot proceed.")
    st.stop()
selected_clutch_code = str(row.get("clutch_code", "") or "").strip()
st.session_state["last_clutch_id"] = clutch_id

creator = (
    os.environ.get("USER")
    or os.environ.get("USERNAME")
    or (getattr(user, "email", "") or "system")
)

# load parents via clutches.cross_id → crosses.* → v11_fish_instance_star
mom_data, dad_data = _load_parents_for_clutch(clutch_id)

c1, c2, c3 = st.columns(3)
with c1:
    _pivot(
        "Clutch — standard fields",
        [
            ("Clutch id", clutch_id),
            ("Clutch code", selected_clutch_code),
            ("Clutch date", row.get("clutch_date") or row.get("clutch_birthday")),
            ("Estimated eggs", row.get("estimated_egg_count")),
            ("Cross", row.get("cross_name_pretty")),
            ("Genotype (pretty)", row.get("genotype_pretty")),
            ("Genotype basecode", row.get("genotype_basecode_code")),
            ("Genotype allele code", row.get("genotype_transgene_allele_code")),
            ("Treatment code", row.get("treatment_code")),
            ("Treat codes", row.get("treat_codes")),
            ("Treatments > transgenes", row.get("treatments_and_transgenes")),
            ("Tx → fluor::tag(pos)", row.get("all_fluor_tag_rollup")),
            ("Tx → organelle-fluor", row.get("all_organelle_fluor_rollup")),
        ],
    )

with c2:
    _pivot(
        "Mother — fish + tank (v11_fish_instance_star)",
        [
            ("Fish code", mom_data.get("fish_code")),
            ("Tank code", mom_data.get("tank_code")),
            ("Tank status", mom_data.get("tank_status")),
            ("Genotype (pretty)", mom_data.get("genotype_pretty")),
            ("Genotype basecode", mom_data.get("genotype_basecode_code")),
            ("Genotype allele code", mom_data.get("genotype_transgene_allele_code")),
            ("Treatment code", mom_data.get("treatment_code")),
            ("Treatments > transgenes", mom_data.get("treatments_and_transgenes")),
            ("Tx → fluor::tag(pos)", mom_data.get("all_fluor_tag_rollup")),
            ("Tx → organelle-fluor", mom_data.get("all_organelle_fluor_rollup")),
        ],
    )

with c3:
    _pivot(
        "Father — fish + tank (v11_fish_instance_star)",
        [
            ("Fish code", dad_data.get("fish_code")),
            ("Tank code", dad_data.get("tank_code")),
            ("Tank status", dad_data.get("tank_status")),
            ("Genotype (pretty)", dad_data.get("genotype_pretty")),
            ("Genotype basecode", dad_data.get("genotype_basecode_code")),
            ("Genotype allele code", dad_data.get("genotype_transgene_allele_code")),
            ("Treatment code", dad_data.get("treatment_code")),
            ("Treatments > transgenes", dad_data.get("treatments_and_transgenes")),
            ("Tx → fluor::tag(pos)", dad_data.get("all_fluor_tag_rollup")),
            ("Tx → organelle-fluor", dad_data.get("all_organelle_fluor_rollup")),
        ],
    )

# ── 2. Select treatments to add ----------------------------------------------
st.subheader("2. Select treatments to add")

tc1, tc2 = st.columns([1, 2])
with tc1:
    kind_filter = st.selectbox(
        "Filter by kind_code",
        options=["", "plasmid", "rna", "dye", "crispr"],
        format_func=lambda x: x or "Any",
        index=0,
    )
with tc2:
    search_tx = st.text_input("Search treatments (code / text)", value="")

treat_df = _load_treatments(kind_filter, search_tx)
st.caption(f"{len(treat_df)} treatment(s) in library")

selected_ids: List[str] = []
selected_preview = pd.DataFrame()

if treat_df.empty:
    st.info("No treatments match the current filters.")
else:
    df_t = treat_df.copy()

    # Insert checkbox *once*
    df_t.insert(0, "✓", False)

    # Reorder to standard treatment fields (NO duplicate '✓')
    ordered_cols = [
        "✓",
        "treatment_code",
        "genotype_basecode_code",
        "materials_by_kind",
        "all_fluor_tag_rollup",
        "all_organelle_fluor_rollup",
        "kind_code",
        "treat_text",
        "created_at",
    ]
    ordered_cols += [c for c in df_t.columns if c not in ordered_cols]

    df_t = df_t[ordered_cols]

    eg_tx = st.data_editor(
        df_t,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False),
            "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
        },
        key="treatment_picker_v11",
    )

    sel_mask_tx = eg_tx.get("✓", pd.Series(False, index=eg_tx.index)).fillna(False).astype(bool)
    picked_tx = eg_tx.loc[sel_mask_tx].reset_index(drop=True)
    st.caption(f"Selected treatments: {len(picked_tx)}")

    if not picked_tx.empty:
        # preview df only with standard fields (no checkbox)
        selected_preview = picked_tx[
            [
                "treatment_code",
                "genotype_basecode_code",
                "materials_by_kind",
                "all_fluor_tag_rollup",
                "all_organelle_fluor_rollup",
                "kind_code",
                "treat_text",
            ]
        ].copy()
        # map IDs directly
        if "treatment_id" in picked_tx.columns:
            selected_ids = picked_tx["treatment_id"].astype(str).tolist()

# ── Selected treatments preview ----------------------------------------------
st.subheader("Selected treatments — preview")

if selected_preview.empty:
    st.info("No treatments selected yet.")
else:
    st.data_editor(
        selected_preview,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=True,
        key="selected_treatments_preview_ro",
    )

# ── Save ---------------------------------------------------------------------
st.subheader("Save")

if st.button("➕ Attach selected treatments to this clutch", use_container_width=True):
    if not selected_ids:
        st.warning("No treatments selected.")
    else:
        n, errs = _attach_treatments(clutch_id, creator, selected_ids)
        msg = f"Attached {n} treatment(s) to clutch {selected_clutch_code or clutch_id[:8]}."
        if n:
            st.success(msg)
        else:
            st.info(msg)
        if errs:
            st.warning("Some treatments could not be attached:\n- " + "\n- ".join(errs))
        st.session_state["just_attached"] = True

# ── 3. Existing treatments on this clutch ------------------------------------
st.subheader("3. Existing treatments on this clutch")

treat_df_existing = _load_clutch_treatments(clutch_id)
if treat_df_existing.empty:
    st.info("No treatments attached yet.")
else:
    st.data_editor(
        treat_df_existing[
            [
                "created_at",
                "treatment_code",
                "genotype_basecode_code",
                "materials_by_kind",
                "all_fluor_tag_rollup",
                "all_organelle_fluor_rollup",
                "kind_code",
                "treat_text",
            ]
        ],
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=True,
        key="clutch_treatments_existing_ro",
    )