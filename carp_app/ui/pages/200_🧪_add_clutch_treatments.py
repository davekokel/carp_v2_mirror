# carp_app/ui/pages/200_🧪_add_clutch_treatments.py
from __future__ import annotations
import sys, pathlib, os
from datetime import date, timedelta
from typing import List, Dict, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root on sys.path
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()

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

CLUTCHES_VIEW = "public.v_clutches_overview"

# ── Guards / helpers ---------------------------------------------------------


def _table_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        n = pd.read_sql(
            text("""
              select count(*)::int as n
              from information_schema.tables
              where table_schema=:s and table_name=:n
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


_HAS_V_RNA = _view_exists("public", "v_rna_plasmids")

if not _view_exists("public", "v_clutches_overview"):
    st.error("public.v_clutches_overview is missing; please apply that migration first.")
    st.stop()

if not _table_exists("public", "clutch_instances"):
    st.error("Required table public.clutch_instances not found.")
    st.stop()

# ── Data loaders / utils -----------------------------------------------------


def _safe(q: str, p=None) -> pd.DataFrame:
    with _eng().begin() as cx:
        return pd.read_sql(text(q), cx, params=p or {})


def _load_clutches(d_from, d_to, created_by: str, q: str, most_recent: bool) -> pd.DataFrame:
    """
    Pull clutches from v_clutches_overview, include clutch_instance_id for resolution,
    and roll up treatments via treated_clutches -> join_clutch_treatments -> treatments.treat_code.
    """
    where: List[str] = []
    params: Dict[str, Any] = {}

    if not most_recent:
        where.append("v.clutch_created_at::date BETWEEN :d1 AND :d2")
        params.update({"d1": d_from, "d2": d_to})

    # created_by is currently a placeholder; no column yet
    if created_by.strip():
        where.append("TRUE")

    qnorm = (q or "").strip()
    if qnorm:
        params["q"] = f"%{qnorm}%"
        where.append("""(
            COALESCE(v.clutch_code,'')        ILIKE :q OR
            COALESCE(v.cross_code,'')         ILIKE :q OR
            COALESCE(v.clutch_genotype,'')    ILIKE :q OR
            COALESCE(v.clutch_genotype_pretty,'') ILIKE :q OR
            COALESCE(v.tank_pair_code,'')     ILIKE :q OR
            COALESCE(v.mom_fish_code,'')      ILIKE :q OR
            COALESCE(v.dad_fish_code,'')      ILIKE :q
        )""")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = text(f"""
      WITH base AS (
        SELECT
          v.clutch_instance_id,
          COALESCE(v.clutch_code, 'CI-' || LEFT(v.clutch_instance_id::text, 8)) AS clutch_code,
          v.clutch_date                     AS clutch_birthday,
          COALESCE(v.cross_code, v.tank_pair_code || ' @ ' || COALESCE(v.cross_date::text,'')) AS cross_name_pretty,
          COALESCE(v.clutch_genotype_pretty, v.clutch_genotype, '') AS clutch_genotype_pretty,
          v.clutch_created_at,
          v.tank_pair_code,
          v.mom_fish_code,
          v.dad_fish_code,
          v.mom_genotype,
          v.dad_genotype,
          v.mom_fusions,
          v.dad_fusions
        FROM {CLUTCHES_VIEW} v
        {where_sql}
        ORDER BY v.clutch_created_at DESC NULLS LAST, v.clutch_code
        LIMIT 1000
      ),
      tx_codes AS (
        SELECT
          s.clutch_instance_id,
          COALESCE(string_agg(s.code, '+' ORDER BY s.code), '') AS codes
        FROM (
          SELECT DISTINCT
            tc.clutch_instance_id,
            NULLIF(t.treat_code,'') AS code
          FROM public.treated_clutches tc
          JOIN public.join_clutch_treatments j ON j.treated_clutch_id = tc.id
          LEFT JOIN public.treatments t        ON t.id = j.treatment_id
          WHERE NULLIF(t.treat_code,'') IS NOT NULL
        ) s
        GROUP BY s.clutch_instance_id
      ),
      tx_count AS (
        SELECT
          tc.clutch_instance_id,
          COUNT(t.id)::int AS n_effective
        FROM public.treated_clutches tc
        JOIN public.join_clutch_treatments j ON j.treated_clutch_id = tc.id
        LEFT JOIN public.treatments t        ON t.id = j.treatment_id
        GROUP BY tc.clutch_instance_id
      )
      SELECT
        b.clutch_instance_id,
        b.clutch_code,
        b.clutch_birthday,
        b.cross_name_pretty,
        b.clutch_genotype_pretty,
        COALESCE(c.n_effective,0)      AS treatments_count_effective,
        COALESCE(x.codes,'')           AS clutch_treatments_codes,
        b.clutch_created_at,
        b.tank_pair_code,
        b.mom_fish_code,
        b.dad_fish_code,
        b.mom_genotype,
        b.dad_genotype,
        b.mom_fusions,
        b.dad_fusions
      FROM base b
      LEFT JOIN tx_count c ON c.clutch_instance_id = b.clutch_instance_id
      LEFT JOIN tx_codes x ON x.clutch_instance_id = b.clutch_instance_id
    """)

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    df["treatments_count_effective"] = (
        pd.to_numeric(df["treatments_count_effective"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    # ensure all expected columns exist
    ui_cols = [
        "clutch_instance_id",
        "clutch_code",
        "clutch_birthday",
        "cross_name_pretty",
        "clutch_genotype_pretty",
        "treatments_count_effective",
        "clutch_treatments_codes",
        "clutch_created_at",
        "tank_pair_code",
        "mom_fish_code",
        "dad_fish_code",
        "mom_genotype",
        "dad_genotype",
        "mom_fusions",
        "dad_fusions",
    ]
    for c in ui_cols:
        if c not in df.columns:
            df[c] = None
    return df[ui_cols]


def _load_plasmids(search: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        return pd.read_sql(
            text("""
              SELECT code, name, COALESCE(nickname,'') AS nickname, created_at
              FROM public.plasmids
              WHERE (:q = '' OR COALESCE(code,'') ILIKE :ql OR COALESCE(name,'') ILIKE :ql OR COALESCE(nickname,'') ILIKE :ql)
              ORDER BY COALESCE(created_at, now()) DESC NULLS LAST
              LIMIT 1000
            """),
            cx,
            params={"q": search or "", "ql": f"%{search or ''}%"},
        )


def _load_rnas(search: str) -> pd.DataFrame:
    s = (search or "").strip()
    with _eng().begin() as cx:
        if _HAS_V_RNA:
            q = """
              SELECT code, name, COALESCE(nickname,'') AS nickname, created_at
              FROM public.v_rna_plasmids
              {where}
              ORDER BY COALESCE(created_at, now()) DESC NULLS LAST
              LIMIT 1000
            """
            where = (
                "WHERE COALESCE(code,'') ILIKE :q OR COALESCE(name,'') ILIKE :q OR COALESCE(nickname,'') ILIKE :q"
                if s
                else ""
            )
            return pd.read_sql(text(q.format(where=where)), cx, params=({"q": f"%{s}%"} if s else {}))

        if s:
            return pd.read_sql(
                text("""
                  SELECT
                    rna_code AS code,
                    COALESCE(nickname, rna_code) AS name,
                    COALESCE(notes,'') AS nickname,
                    created_at
                  FROM public.rnas
                  WHERE COALESCE(rna_code,'') ILIKE :q
                     OR COALESCE(nickname,'') ILIKE :q
                     OR COALESCE(notes,'')    ILIKE :q
                  ORDER BY COALESCE(created_at, now()) DESC NULLS LAST, rna_code
                  LIMIT 1000
                """),
                cx,
                params={"q": f"%{s}%"},
            )
        return pd.read_sql(
            text("""
              SELECT
                rna_code AS code,
                COALESCE(nickname, rna_code) AS name,
                COALESCE(notes,'') AS nickname,
                created_at
              FROM public.rnas
              ORDER BY COALESCE(created_at, now()) DESC NULLS LAST, rna_code
              LIMIT 1000
            """),
            cx,
        )


def _load_dyes(search: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        return pd.read_sql(
            text("""
              SELECT dye_code AS code,
                     dye_name AS name,
                     COALESCE(localization,'') AS localization,
                     excitation_nm, emission_nm
              FROM public.dyes
              WHERE (:q = '' OR
                     COALESCE(dye_code,'') ILIKE :ql OR
                     COALESCE(dye_name,'') ILIKE :ql OR
                     COALESCE(localization,'') ILIKE :ql)
              ORDER BY COALESCE(dye_name, dye_code)
              LIMIT 1000
            """),
            cx,
            params={"q": search or "", "ql": f"%{search or ''}%"},
        )


def _load_crisprs(search: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        return pd.read_sql(
            text("""
              SELECT knockin_code AS code,
                     COALESCE(description,'') AS name,
                     created_at
              FROM public.crispr_knockins
              WHERE (:q = '' OR
                     COALESCE(knockin_code,'') ILIKE :ql OR
                     COALESCE(description,'')  ILIKE :ql)
              ORDER BY COALESCE(created_at, now()) DESC NULLS LAST
              LIMIT 1000
            """),
            cx,
            params={"q": search or "", "ql": f"%{search or ''}%"},
        )

# Treatments on this run (via treated_clutches)


def _load_instance_treatments(clutch_instance_id: str) -> pd.DataFrame:
    """
    List treatments linked to this clutch via treated_clutches → join_clutch_treatments → treatments.
    """
    with _eng().begin() as cx:
        sql = text("""
          SELECT
            jct.created_at,
            t.kind_code                           AS material_type,
            t.treat_code                          AS material_code,
            COALESCE(t.treat_text, t.treat_code)  AS material_name,
            ''::text                              AS notes,
            COALESCE(t.created_by,'')             AS created_by,
            tc.treated_clutch_code,
            ''::text                              AS group_label
          FROM public.treated_clutches tc
          JOIN public.join_clutch_treatments jct
               ON jct.treated_clutch_id = tc.id
          LEFT JOIN public.treatments t
               ON t.id = jct.treatment_id
          WHERE tc.clutch_instance_id = CAST(:cid AS uuid)
          ORDER BY jct.created_at DESC NULLS LAST
        """)
        return pd.read_sql(sql, cx, params={"cid": clutch_instance_id})

# Insert selected items: ensure a treatments row exists, then link via join_clutch_treatments


def _insert_instance_treatments(
    clutch_instance_id: str,
    treated_clutch_id: str,
    created_by: str,
    items: List[Dict[str, Any]],
):
    """
    For each selected item, ensure a row exists in public.treatments(kind_code, treat_code, treat_text, created_by),
    then link it via public.join_clutch_treatments(treated_clutch_id, treatment_id, created_at).
    """
    inserted, errs = 0, []
    with _eng().begin() as cx:
        for it in items:
            kind = str(it.get("treatment_type") or "").strip()
            code = str(it.get("code") or "").strip()
            name = str(it.get("name") or "").strip()
            if not kind or not code:
                errs.append("<missing kind/code> → skipped")
                continue

            tid = pd.read_sql(
                text("SELECT id::text AS id FROM public.treatments WHERE kind_code=:k AND treat_code=:c LIMIT 1"),
                cx,
                params={"k": kind, "c": code},
            )
            if tid.empty:
                tid = pd.read_sql(
                    text("""
                      INSERT INTO public.treatments (id, treat_code, kind_code, treat_text, created_by, created_at)
                      VALUES (gen_random_uuid(), :c, :k, NULLIF(:name,''), :who, now())
                      RETURNING id::text AS id
                    """),
                    cx,
                    params={"k": kind, "c": code, "name": name, "who": created_by or ""},
                )
            treatment_id = tid["id"].iloc[0]

            exists = pd.read_sql(
                text("""
                  SELECT 1
                  FROM public.join_clutch_treatments
                  WHERE treated_clutch_id = CAST(:gid AS uuid)
                    AND treatment_id      = CAST(:tid AS uuid)
                  LIMIT 1
                """),
                cx,
                params={"gid": treated_clutch_id, "tid": treatment_id},
            )
            if exists.empty:
                cx.execute(
                    text("""
                      INSERT INTO public.join_clutch_treatments (treated_clutch_id, treatment_id, created_at)
                      VALUES (CAST(:gid AS uuid), CAST(:tid AS uuid), now())
                    """),
                    {"gid": treated_clutch_id, "tid": treatment_id},
                )
                inserted += 1
    return inserted, errs

# Auto-create a treated-clutch group on every save


def _create_autogroup(ci_id: str, clutch_code: str, who: str) -> dict:
    """
    Always return a new treated group for this clutch:
    - Ensure baseline "<base>#0" exists
    - Create "<base>#N" where N is max existing + 1
    """
    base = clutch_code.strip() if clutch_code else f"CL-{ci_id[:8]}"
    with _eng().begin() as cx:
        # ensure baseline #0 exists
        cx.execute(
            text("""
              INSERT INTO public.treated_clutches (clutch_instance_id, treated_clutch_code)
              VALUES (CAST(:cid AS uuid), :code)
              ON CONFLICT (clutch_instance_id, treated_clutch_code) DO NOTHING
            """),
            {"cid": ci_id, "code": f"{base}#0"},
        )

        # compute next suffix
        max_n = pd.read_sql(
            text("""
              SELECT COALESCE(
                       MAX( (regexp_match(treated_clutch_code, '#(\\d+)$'))[1]::int ),
                       0
                     ) AS n
              FROM public.treated_clutches
              WHERE clutch_instance_id = CAST(:cid AS uuid)
                AND treated_clutch_code LIKE :prefix || '%'
            """),
            cx,
            params={"cid": ci_id, "prefix": f"{base}#"},
        ).iloc[0]["n"]

        new_code = f"{base}#{int(max_n) + 1}"

        m = cx.execute(
            text("""
              INSERT INTO public.treated_clutches (clutch_instance_id, treated_clutch_code)
              VALUES (CAST(:cid AS uuid), :code)
              RETURNING id::text AS treated_clutch_id, treated_clutch_code
            """),
            {"cid": ci_id, "code": new_code},
        ).mappings().first()
    return dict(m)

# ── Filters + clutch picker --------------------------------------------------


with st.form("filters_form", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
    with c1:
        d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2:
        d2 = st.date_input("To", value=today + timedelta(days=14))
    with c3:
        created_by = st.text_input("Created by (plan/instance)", value="")
    with c4:
        qtxt = st.text_input("Search (code/cross/clutch/genotype)", value="")
    r1, r2 = st.columns([1, 3])
    with r1:
        ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2:
        st.form_submit_button("Apply", use_container_width=True)

clutches = _load_clutches(d1, d2, created_by, qtxt, ignore_dates)
st.caption(f"{len(clutches)} clutch(es)")

if clutches.empty:
    st.info("No clutches found with the current filters.")
    st.stop()

dfv = clutches.copy()
dfv.insert(0, "✓ Select", False)
last_ci = st.session_state.get("last_ci")
if last_ci:
    dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
        "clutch_created_at": st.column_config.DatetimeColumn("clutch_created_at", disabled=True),
        "treatments_count_effective": st.column_config.NumberColumn(
            "treatments_count_effective", format="%d"
        ),
    },
    key="ci_only_picker_v1",
)

sel_mask = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False).astype(bool)
picked = dfv.loc[sel_mask, :].reset_index(drop=True)

if picked.empty:
    st.info("Select a clutch row (CI-… preferred) and attach treatments below.")
    st.stop()

row = picked.iloc[0]

# Prefer id; code only for display
clutch_instance_id = str(row.get("clutch_instance_id", "") or "").strip()
if not clutch_instance_id:
    st.error("Selected row is missing clutch_instance_id; cannot proceed.")
    st.stop()
selected_clutch_code = str(row.get("clutch_code", "") or "").strip()
st.session_state["last_ci"] = selected_clutch_code

# For context (not required for save), get cross id
with _eng().begin() as cx:
    r = pd.read_sql(
        text("""
          SELECT ci.cross_instance_id::text AS cross_instance_id
          FROM public.clutch_instances ci
          WHERE ci.id = CAST(:cid AS uuid)
          LIMIT 1
        """),
        cx,
        params={"cid": clutch_instance_id},
    )
if r.empty:
    st.error("Could not resolve cross_instance_id for the selected clutch.")
    st.stop()
cross_instance_id = r["cross_instance_id"].iloc[0]

creator = (
    os.environ.get("USER")
    or os.environ.get("USERNAME")
    or (getattr(user, "email", "") or "system")
)

# ── Selected clutch — context (with headers for each table) ------------------
st.subheader("Selected clutch — context")

def _pivot(title: str, rows: List[tuple[str, Any]]):
    dfp = pd.DataFrame(rows, columns=["Field", "Value"])
    st.markdown(f"**{title}**")
    st.dataframe(dfp, hide_index=True, use_container_width=True)

c1, c2, c3 = st.columns(3)

with c1:
    _pivot(
        "Clutch",
        [
            ("Clutch instance id", clutch_instance_id),
            ("Clutch code", selected_clutch_code),
            ("Clutch birthday", row.get("clutch_birthday")),
            ("Cross", row.get("cross_name_pretty")),
            ("Tank pair code", row.get("tank_pair_code")),
            ("# treatments", row.get("treatments_count_effective")),
            ("Treatment codes", row.get("clutch_treatments_codes")),
        ],
    )

with c2:
    _pivot(
        "Mother",
        [
            ("Fish code", row.get("mom_fish_code")),
            ("Genotype", row.get("mom_genotype")),
            ("Fusions", row.get("mom_fusions")),
        ],
    )

with c3:
    _pivot(
        "Father",
        [
            ("Fish code", row.get("dad_fish_code")),
            ("Genotype", row.get("dad_genotype")),
            ("Fusions", row.get("dad_fusions")),
        ],
    )

# ── Add treatments UI --------------------------------------------------------
st.subheader("Add treatments to this clutch instance")
tabs = st.tabs(["Plasmids", "RNAs", "Dyes", "CRISPR knockins"])

# Plasmids
with tabs[0]:
    c1, c2 = st.columns([2, 1])
    with c1:
        q_pl = st.text_input("Search plasmids (code / name / nickname / fluors / resistance)", value="")
    with c2:
        note_pl = st.text_input("Note for selected plasmids", value="")
    df_pl = _load_plasmids(q_pl)
    st.caption(f"{len(df_pl)} plasmid(s)")
    if df_pl.empty:
        picked_pl = pd.DataFrame()
    else:
        df_pl = df_pl.copy()
        if "✓ Select" not in df_pl.columns:
            df_pl.insert(0, "✓ Select", False)
        eg_pl = st.data_editor(
            df_pl,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False)},
            key="plasmids_editor_ci_v1",
        )
        sel_mask_pl = (
            eg_pl.get("✓ Select").fillna(False).astype(bool)
            if "✓ Select" in eg_pl.columns
            else pd.Series([], dtype=bool)
        )
        picked_pl = eg_pl.loc[sel_mask_pl].reset_index(drop=True)
        st.caption(f"Selected plasmids: {len(picked_pl)}")
        if not picked_pl.empty:
            picked_pl = picked_pl.assign(
                treatment_type="plasmid",
                code=picked_pl["code"].astype(str),
                name=picked_pl["name"].astype(str),
                _note=note_pl,
            )
    st.session_state["_picked_pl"] = picked_pl if "picked_pl" in locals() else pd.DataFrame()

# RNAs
with tabs[1]:
    c1, c2 = st.columns([2, 1])
    with c1:
        q_rna = st.text_input("Search RNAs (code / nickname / notes)", value="")
    with c2:
        note_rna = st.text_input("Note for selected RNAs", value="")
    df_rna = _load_rnas(q_rna)
    src = "v_rna_plasmids" if _HAS_V_RNA else "public.rnas"
    st.caption(f"{len(df_rna)} RNA(s) • source: {src}")
    if df_rna.empty:
        picked_rna = pd.DataFrame()
        st.info("No RNAs match your search.")
    else:
        df_rna = df_rna.copy()
        if "✓ Select" not in df_rna.columns:
            df_rna.insert(0, "✓ Select", False)
        eg_rna = st.data_editor(
            df_rna,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False)},
            key="rnas_editor_ci_v1",
        )
        sel_mask_rna = (
            eg_rna.get("✓ Select").fillna(False).astype(bool)
            if "✓ Select" in eg_rna.columns
            else pd.Series([], dtype=bool)
        )
        picked_rna = eg_rna.loc[sel_mask_rna].reset_index(drop=True)
        st.caption(f"Selected RNAs: {len(picked_rna)}")

        def _canon_rna(series: pd.Series) -> pd.Series:
            s = series.astype(str)
            return s.where(s.str.match(r"^RNA\(.+\)$"), "RNA(" + s + ")")

        if not picked_rna.empty:
            picked_rna = picked_rna.assign(
                treatment_type="rna",
                code=_canon_rna(picked_rna["code"]),
                name=picked_rna["name"].astype(str),
                _note=note_rna,
            )
    st.session_state["_picked_rna"] = picked_rna if "picked_rna" in locals() else pd.DataFrame()

# Dyes
with tabs[2]:
    c1, c2 = st.columns([2, 1])
    with c1:
        q_dye = st.text_input("Search dyes (code / name / localization)", value="")
    with c2:
        note_dye = st.text_input("Note for selected dyes", value="")
    df_dye = _load_dyes(q_dye)
    st.caption(f"{len(df_dye)} dye(s)")
    if df_dye.empty:
        picked_dye = pd.DataFrame()
    else:
        df_dye = df_dye.copy()
        if "✓ Select" not in df_dye.columns:
            df_dye.insert(0, "✓ Select", False)
        eg_dye = st.data_editor(
            df_dye,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False)},
            key="dyes_editor_ci_v1",
        )
        sel_mask_dye = (
            eg_dye.get("✓ Select").fillna(False).astype(bool)
            if "✓ Select" in eg_dye.columns
            else pd.Series([], dtype=bool)
        )
        picked_dye = eg_dye.loc[sel_mask_dye].reset_index(drop=True)
        st.caption(f"Selected dyes: {len(picked_dye)}")
        if not picked_dye.empty:
            picked_dye = picked_dye.assign(
                treatment_type="dye",
                code=picked_dye["code"].astype(str),
                name=picked_dye["name"].astype(str),
                _note=note_dye,
            )
    st.session_state["_picked_dye"] = picked_dye if "picked_dye" in locals() else pd.DataFrame()

# CRISPR knockins
with tabs[3]:
    c1, c2 = st.columns([2, 1])
    with c1:
        q_cr = st.text_input("Search CRISPR knockins (code / description)", value="")
    with c2:
        note_cr = st.text_input("Note for selected knockins", value="")
    df_cr = _load_crisprs(q_cr)
    st.caption(f"{len(df_cr)} CRISPR knockin(s)")
    if df_cr.empty:
        picked_cr = pd.DataFrame()
    else:
        df_cr = df_cr.copy()
        if "✓ Select" not in df_cr.columns:
            df_cr.insert(0, "✓ Select", False)
        eg_cr = st.data_editor(
            df_cr,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False)},
            key="crispr_editor_ci_v1",
        )
        sel_mask_cr = (
            eg_cr.get("✓ Select").fillna(False).astype(bool)
            if "✓ Select" in eg_cr.columns
            else pd.Series([], dtype=bool)
        )
        picked_cr = eg_cr.loc[sel_mask_cr].reset_index(drop=True)
        st.caption(f"Selected CRISPR knockins: {len(picked_cr)}")
        if not picked_cr.empty:
            picked_cr = picked_cr.assign(
                treatment_type="crispr",
                code=picked_cr["code"].astype(str),
                name=picked_cr["name"].astype(str),
                _note=note_cr,
            )
    st.session_state["_picked_cr"] = picked_cr if "picked_cr" in locals() else pd.DataFrame()

# ── Preview selected items ---------------------------------------------------
st.divider()
st.subheader("Preview selected treatments")


def _preview_from_state() -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for key in ("_picked_pl", "_picked_rna", "_picked_dye", "_picked_cr"):
        df = st.session_state.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty:
            tmp = df.copy()
            if "_note" not in tmp.columns:
                tmp["_note"] = ""
            frames.append(
                tmp[["treatment_type", "code", "name", "_note"]].rename(
                    columns={
                        "treatment_type": "material_type",
                        "code": "material_code",
                        "name": "material_name",
                        "_note": "notes",
                    }
                )
            )
    if not frames:
        return pd.DataFrame(
            columns=[
                "treated_clutch_code",
                "created_at",
                "material_type",
                "material_code",
                "material_name",
                "notes",
                "created_by",
            ]
        )
    out = pd.concat(frames, ignore_index=True)
    out.insert(0, "treated_clutch_code", f"T({selected_clutch_code or ('CI-' + clutch_instance_id[:8])})-next")
    out.insert(1, "created_at", pd.Timestamp.utcnow())
    out["created_by"] = (
        os.environ.get("USER") or os.environ.get("USERNAME") or (getattr(user, "email", "") or "system")
    )
    return out[
        [
            "treated_clutch_code",
            "created_at",
            "material_type",
            "material_code",
            "material_name",
            "notes",
            "created_by",
        ]
    ]


preview_df = _preview_from_state()
st.caption(f"{len(preview_df)} item(s) selected")

if preview_df.empty:
    st.info("No treatments selected yet. Pick items in the tabs above to see them here.")
else:
    st.data_editor(
        preview_df,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=True,
        column_config={
            "treated_clutch_code": st.column_config.TextColumn("treated_clutch_code", disabled=True),
            "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
            "material_type": st.column_config.TextColumn("material_type", disabled=True),
            "material_code": st.column_config.TextColumn("material_code", disabled=True),
            "material_name": st.column_config.TextColumn("material_name", disabled=True),
            "notes": st.column_config.TextColumn("notes", disabled=True),
            "created_by": st.column_config.TextColumn("created_by", disabled=True),
        },
        key="preview_selected_treatments_ro",
    )

# ── Save actions (single button) — auto-group per click ----------------------
st.subheader("Save")
note_all = st.text_input("Note for selected treatments (optional)", value="")


def _collect_items(df_sel: pd.DataFrame) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if df_sel is not None and not df_sel.empty:
        for _, r in df_sel.iterrows():
            items.append(
                {
                    "treatment_type": str(r.get("treatment_type") or ""),
                    "code": str(r.get("code") or ""),
                    "name": str(r.get("name") or ""),
                    "note": str(r.get("_note") or note_all or ""),
                }
            )
    return items


if st.button("➕ Attach selected treatments (new group)", use_container_width=True, key="attach_all_ci_v1"):
    items: List[Dict[str, Any]] = []
    items += _collect_items(st.session_state.get("_picked_pl", pd.DataFrame()))
    items += _collect_items(st.session_state.get("_picked_rna", pd.DataFrame()))
    items += _collect_items(st.session_state.get("_picked_dye", pd.DataFrame()))
    items += _collect_items(st.session_state.get("_picked_cr", pd.DataFrame()))

    if not items:
        st.warning("No treatments selected.")
        st.stop()

    creator = (
        os.environ.get("USER")
        or os.environ.get("USERNAME")
        or (getattr(user, "email", "") or "system")
    )
    grp = _create_autogroup(clutch_instance_id, selected_clutch_code, creator)
    n, errs = _insert_instance_treatments(clutch_instance_id, grp["treated_clutch_id"], creator, items)
    st.session_state["treatments_result"] = {"instance": n, "errs": errs, "group_code": grp["treated_clutch_code"]}

# ── Feedback -----------------------------------------------------------------
_tmsg = st.session_state.pop("treatments_result", None)
if _tmsg:
    msg = f"Attached {_tmsg.get('instance',0)} treatment(s)"
    if _tmsg.get("group_code"):
        msg += f" to group {_tmsg['group_code']}"
    st.success(msg + ".")
    if _tmsg.get("errs"):
        st.warning("Some items were skipped:\n- " + "\n- ".join(_tmsg["errs"]))

# ── Updated run summary (per group) -----------------------------------------
st.subheader("Updated run summary (per group)")

grp_sql = text("""
  WITH s AS (
    SELECT DISTINCT
      tc.treated_clutch_code,
      tc.created_at              AS group_created_at,
      tc.id                      AS tc_id,
      tc.clutch_instance_id,
      NULLIF(t.treat_code,'')    AS code
    FROM public.treated_clutches tc
    LEFT JOIN public.join_clutch_treatments jct
           ON jct.treated_clutch_id = tc.id
    LEFT JOIN public.treatments t
           ON t.id = jct.treatment_id
    WHERE tc.clutch_instance_id = CAST(:cid AS uuid)
  )
  SELECT
    s.treated_clutch_code,
    s.group_created_at,
    COUNT(*) FILTER (WHERE s.code IS NOT NULL)::int AS treatments_count_group,
    COALESCE(string_agg(s.code, '+' ORDER BY s.code), '') AS treatments_codes_group
  FROM s
  GROUP BY s.treated_clutch_code, s.group_created_at
  ORDER BY s.group_created_at ASC, s.treated_clutch_code
""")

with _eng().begin() as cx:
    gdf = pd.read_sql(grp_sql, cx, params={"cid": clutch_instance_id})

if gdf.empty:
    st.info("No treatment groups yet for this clutch.")
else:
    st.data_editor(
        gdf,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=True,
        column_config={
            "treated_clutch_code":    st.column_config.TextColumn("treated_clutch_code", disabled=True),
            "group_created_at":       st.column_config.DatetimeColumn("created_at", disabled=True),
            "treatments_count_group": st.column_config.NumberColumn("# tx", disabled=True, format="%d"),
            "treatments_codes_group": st.column_config.TextColumn("treatments (codes)", disabled=True),
        },
        key="summary_groups_ro",
    )

# ── Treatments on this run ---------------------------------------------------
st.subheader("Treatments on this run")
treat_df = _load_instance_treatments(clutch_instance_id)

if treat_df.empty:
    st.info("No treatments attached yet.")
else:
    _norm = lambda s: (s or "").strip().lower()
    dedup = (
        treat_df.assign(
            _mt=treat_df["material_type"].map(_norm),
            _mc=treat_df["material_code"].map(_norm),
        )
        .drop_duplicates(["_mt", "_mc"])
        .sort_values("created_at", ascending=False)
    )
    live_count = int(dedup.shape[0])
    live_pretty = " + ".join(dedup["material_code"].tolist())
    st.info(f"Live treatments on this run → count: {live_count} | {live_pretty}")

    preferred = [
        "treated_clutch_code",
        "created_at",
        "material_type",
        "material_code",
        "material_name",
        "notes",
        "created_by",
    ]
    cols = [c for c in preferred if c in treat_df.columns] + [
        c for c in treat_df.columns if c not in preferred and c != "group_label"
    ]

    st.data_editor(
        treat_df[cols],
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=True,
        key="treatments_on_run_ro",
    )