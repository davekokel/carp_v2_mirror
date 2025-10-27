from __future__ import annotations
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.lib.time import utc_now

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

import os, subprocess
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from carp_app.ui.lib.app_ctx import get_engine as _create_engine
from carp_app.ui.lib.labels_components import build_tank_labels_pdf

@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

st.set_page_config(page_title="CARP — Search Fish → Tanks", page_icon="🔎", layout="wide")

# ───────────── helpers (no caching on DB reads to avoid stale results) ─────────────
def _normalize_q(q_raw: str) -> str | None:
    q = (q_raw or "").strip()
    return q or None

def _coerce_strings(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _load_fish_overview(q: str | None, limit: int) -> pd.DataFrame:
    sql = text("""
      WITH base AS (
        SELECT
          v.fish_uuid,
          v.fish_code,
          v.fish_name,
          v.fish_nickname,
          v.genetic_background,
          v.line_building_stage,
          v.date_birth,
          v.n_active_tanks,
          v.allele_number,
          v.allele_code,
          v.transgene_pretty,
          v.genotype_rollup,
          f.created_at
        FROM public.v_fish_rich v
        JOIN public.fish f ON f.fish_uuid = v.fish_uuid
      )
      SELECT *
      FROM base
      WHERE (:q IS NULL)
         OR (fish_code ILIKE :q
          OR COALESCE(fish_name,'') ILIKE :q
          OR COALESCE(fish_nickname,'') ILIKE :q
          OR COALESCE(genetic_background,'') ILIKE :q
          OR COALESCE(line_building_stage,'') ILIKE :q
          OR COALESCE(transgene_pretty,'') ILIKE :q
          OR COALESCE(genotype_rollup,'') ILIKE :q)
      ORDER BY created_at DESC NULLS LAST, fish_code
      LIMIT :lim
    """)
    params = {"q": (f"%{q}%" if q else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)

def _load_tanks_for_codes(codes: list[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=["fish_code","tank_code","status","created_at","container_id"])
    sql = text("""
      SELECT
        v.tank_uuid::text         AS container_id,
        v.tank_code::text         AS tank_code,
        v.status::text            AS status,
        v.fish_code::text         AS fish_code,
        v.created_at::timestamptz AS created_at
      FROM public.v_tanks v
      WHERE v.fish_code = ANY(:codes)
      ORDER BY v.created_at ASC, v.tank_code ASC
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    return _coerce_strings(df)

def _load_fish_rich_all(q: str | None, limit: int) -> pd.DataFrame:
    sql = text("""
      SELECT * FROM public.v_fish_rich v
      WHERE (:q IS NULL)
         OR (v.fish_code ILIKE :q
          OR COALESCE(v.fish_name,'') ILIKE :q
          OR COALESCE(v.fish_nickname,'') ILIKE :q
          OR COALESCE(v.genetic_background,'') ILIKE :q
          OR COALESCE(v.line_building_stage,'') ILIKE :q
          OR COALESCE(v.transgene_pretty,'') ILIKE :q OR COALESCE(v.genotype_rollup,'') ILIKE :q
          OR COALESCE(v.n_active_tanks::text,'') ILIKE :q)
      ORDER BY v.fish_code
      LIMIT :lim
    """)
    params = {"q": (f"%{q}%" if q else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)

# ───────────── page ─────────────
def main():
    st.title("🔎 Search Fish → Tanks")
    st.caption(f"DB_URL = {os.getenv('DB_URL','')}")

    with st.form("filters", clear_on_submit=False):
        c1, c2 = st.columns([3,1])
        with c1:
            q_raw = st.text_input("Search fish (code/name/nickname/background/allele)", "")
        with c2:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        submitted = st.form_submit_button("Search")

    q = _normalize_q(q_raw)

    df = _load_fish_overview(q, limit)
    if df.empty:
        st.info("No fish match your search.")
        with st.expander("Advanced: full v_fish_rich (all columns)"):
            raw = _load_fish_rich_all(q, limit)
            st.caption(f"{len(raw)} row(s) • columns: {', '.join(raw.columns)}")
            if not raw.empty:
                st.dataframe(raw, use_container_width=True, hide_index=True)
                st.download_button(
                    "⬇︎ Download v_fish_rich.csv",
                    data=raw.to_csv(index=False).encode("utf-8"),
                    file_name=f"v_fish_rich_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
                    type="secondary",
                    mime="text/csv"
                )
        return

    # Rename to display headers
    df = df.rename(columns={
        "fish_code": "Fish code",
        "fish_name": "Fish name",
        "fish_nickname": "Fish nickname",
        "genetic_background": "Genetic background",
        "line_building_stage": "Line-building stage",
        "allele_number": "Allele number",
        "allele_code": "Allele code",
        "transgene_pretty": "Transgene (pretty)",
        "genotype_rollup": "Genotype rollup",
        "n_active_tanks": "Current tanks",
        "date_birth": "Birth date",
        "created_at": "Created time",
    })

    show_cols = [
        "Fish code",
        "Fish name", "Fish nickname",
        "Genetic background", "Line-building stage",
        "Allele number", "Allele code",
        "Transgene (pretty)", "Genotype rollup",
        "Current tanks",
        "Birth date", "Created time",
    ]
    show_cols = [c for c in show_cols if c in df.columns]
    st.subheader(f"Fish ({len(df)} rows)")
    table = df[show_cols].copy()
    table.insert(0, "✓ Select", False)

    # editable table; capture selection directly
    fish_table = st.data_editor(
        table,
        use_container_width=True,
        hide_index=True,
        key="fish_table",
    )

    # Tanks for selected fish
    st.subheader("Tanks for selected fish")
    selected_codes = []
    if isinstance(fish_table, pd.DataFrame) and "✓ Select" in fish_table.columns:
        selected_codes = fish_table.loc[fish_table["✓ Select"] == True, "Fish code"].dropna().astype(str).tolist()

    if not selected_codes:
        st.info("Select one or more fish to show their tanks.")
    else:
        tdf = _load_tanks_for_codes(selected_codes)
        if tdf.empty:
            st.info("No tanks for selected fish.")
        else:
            tcols = [c for c in ["fish_code","tank_code","status","created_at","container_id"] if c in tdf.columns]
            tanks_table = st.data_editor(
                tdf[tcols].copy().assign(**{"✓ Print": False}),
                use_container_width=True,
                hide_index=True,
                key="tank_table",
            )

            # Labels
            st.subheader("Print labels")
            if isinstance(tanks_table, pd.DataFrame) and "✓ Print" in tanks_table.columns:
                chosen_rows = tanks_table.loc[tanks_table["✓ Print"] == True]
            else:
                chosen_rows = pd.DataFrame()

            st.caption(f"{len(chosen_rows)} tank(s) selected for labels")
            if not chosen_rows.empty:
                ids = chosen_rows["container_id"].astype(str).tolist() if "container_id" in chosen_rows.columns else []
                edf = _fetch_enriched_for_containers(ids)
                if edf.empty:
                    st.info("No enriched tank data to print.")
                else:
                    rows = []
                    for _, r in edf.iterrows():
                        dob = r.get("dob")
                        if pd.notna(dob):
                            try:
                                if hasattr(dob, "to_pydatetime"):
                                    dob = dob.to_pydatetime().date()
                                elif isinstance(dob, str):
                                    dob_parsed = pd.to_datetime(dob, errors="coerce")
                                    dob = None if pd.isna(dob_parsed) else dob_parsed.date()
                            except Exception:
                                dob = None
                        rows.append({
                            "tank_code":            r.get("tank_code"),
                            "label":                r.get("tank_code"),
                            "fish_code":            r.get("fish_code") or "",
                            "nickname":             r.get("nickname") or "",
                            "name":                 r.get("name") or "",
                            "genotype":             r.get("genotype", ""),
                            "genetic_background":   r.get("genetic_background") or "",
                            "stage":                r.get("stage") or "",
                            "dob":                  dob,
                        })

                    pdf_bytes = build_tank_labels_pdf(rows)
                    st.download_button(
                        "⬇︎ Download PDF labels (2.4×1.5 • QR)",
                        data=pdf_bytes,
                        file_name=f"tank_labels_2_4x1_5_{utc_now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True,
                    )

if __name__ == "__main__":
    main()

def _fetch_enriched_for_containers(container_ids: list[str]) -> pd.DataFrame:
    # Enrich labels using v_tanks + v_fish_rich (for genotype_pretty) + fish metadata
    want_cols = [
        "container_id","label","status","fish_code",
        "nickname","name","genotype","genetic_background","stage","dob"
    ]
    if not container_ids:
        return pd.DataFrame(columns=want_cols)
    ids = [x for x in container_ids if x]
    if not ids:
        return pd.DataFrame(columns=want_cols)

    sql = text("""
      WITH picked AS (
        SELECT unnest(cast(:ids AS uuid[])) AS container_id
      ),
      vt AS (
        SELECT
            v.tank_uuid::uuid         AS tank_id,
            v.fish_code::text         AS fish_code,
            v.tank_code::text         AS tank_code,
            v.status::text            AS status,
            v.created_at::timestamptz AS created_at
        FROM public.v_tanks v
      ),
      vf AS (
        SELECT
            f.fish_code::text               AS fish_code,
            f.genetic_background::text      AS genetic_background,
            f.line_building_stage::text     AS stage,
            f.date_birth::date              AS dob,
            COALESCE(f.genotype_rollup,'')  AS genotype
        FROM public.v_fish_rich f
      )
      SELECT
        p.container_id::text         AS container_id,
        vt.tank_code                 AS tank_code,
        vt.status                    AS status,
        vt.fish_code                 AS fish_code,
        ''                           AS nickname,
        ''                           AS name,
        vf.genotype                  AS genotype,
        vf.genetic_background        AS genetic_background,
        vf.stage                     AS stage,
        vf.dob                       AS dob
      FROM picked p
      JOIN vt  ON vt.tank_id = p.container_id
      LEFT JOIN vf ON vf.fish_code = vt.fish_code
      ORDER BY vt.created_at ASC, vt.tank_code ASC
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": ids})

    if df.empty:
        return df

    df["label"] = df["tank_code"].fillna("")
    df = _coerce_strings(df)
    return df[[c for c in want_cols if c in df.columns]]

# ─────────────────────────────────────────────────────────────────────────────
# Helper: enrich tank labels with fish/genotype context
# ─────────────────────────────────────────────────────────────────────────────
def _fetch_enriched_for_containers(container_ids: list[str]) -> pd.DataFrame:
    want_cols = [
        "container_id","label","status","fish_code",
        "nickname","name","genotype","genetic_background","stage","dob"
    ]
    if not container_ids:
        return pd.DataFrame(columns=want_cols)
    ids = [x for x in container_ids if x]
    if not ids:
        return pd.DataFrame(columns=want_cols)

    sql = text("""
      WITH picked AS (
        SELECT unnest(cast(:ids AS uuid[])) AS container_id
      ),
      vt AS (
        SELECT
            v.tank_uuid::uuid         AS tank_id,
            v.fish_code::text         AS fish_code,
            v.tank_code::text         AS tank_code,
            v.status::text            AS status,
            v.created_at::timestamptz AS created_at
        FROM public.v_tanks v
      ),
      vf AS (
        SELECT
            f.fish_code::text               AS fish_code,
            f.genetic_background::text      AS genetic_background,
            f.line_building_stage::text     AS stage,
            f.date_birth::date              AS dob,
            COALESCE(f.genotype_rollup,'')  AS genotype
        FROM public.v_fish_rich f
      )
      SELECT
        p.container_id::text         AS container_id,
        vt.tank_code                 AS tank_code,
        vt.status                    AS status,
        vt.fish_code                 AS fish_code,
        ''                           AS nickname,
        ''                           AS name,
        vf.genotype                  AS genotype,
        vf.genetic_background        AS genetic_background,
        vf.stage                     AS stage,
        vf.dob                       AS dob
      FROM picked p
      JOIN vt  ON vt.tank_id = p.container_id
      LEFT JOIN vf ON vf.fish_code = vt.fish_code
      ORDER BY vt.created_at ASC, vt.tank_code ASC
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": ids})

    if df.empty:
        return df

    df["label"] = df["tank_code"].fillna("")
    for c in ["label","fish_code","genotype","genetic_background","stage","status"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)

    if "dob" in df.columns:
        try:
            df["dob"] = pd.to_datetime(df["dob"], errors="coerce").dt.date
        except Exception:
            df["dob"] = None

    return df[[c for c in want_cols if c in df.columns]]
