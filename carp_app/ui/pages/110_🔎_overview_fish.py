# carp_app/ui/pages/110_🔎_overview_fish.py
from __future__ import annotations
import sys, pathlib, os
from typing import Optional, List
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# app libs / auth
from carp_app.lib.time import utc_now
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock():
        return None

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# engine
from carp_app.ui.lib.app_ctx import get_engine as _create_engine

@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

st.set_page_config(page_title="CARP — Search Fish → Tanks", page_icon="🔎", layout="wide")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers (now use v_fish_main as the single canonical view; NO v_fish_unified)
# ─────────────────────────────────────────────────────────────────────────────
def _normalize_q(q_raw: str) -> Optional[str]:
    q = (q_raw or "").strip()
    return q or None

def _coerce_strings(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _load_fish_overview(q: Optional[str], limit: int) -> pd.DataFrame:
    sql = text("""
    WITH mk AS (  -- base-code markers (allele-labelled)
      SELECT
        x.fish_code,
        string_agg(DISTINCT m_expr, ',' ORDER BY m_expr) AS markers
      FROM (
        SELECT
          vm.fish_code,
          CASE
            WHEN vm.allele_name IS NOT NULL AND vm.allele_name <> ''
              THEN vm.transgene_base_code || '(' || vm.allele_name || ')'
            ELSE vm.transgene_base_code
          END AS m_expr
        FROM public.v_fish_main vm
      ) x
      GROUP BY x.fish_code
    ),
    gp AS (  -- genotype_pretty: only allele-named markers
      SELECT
        y.fish_code,
        COALESCE(string_agg(DISTINCT g_expr, ', ' ORDER BY g_expr), '') AS genotype_pretty
      FROM (
        SELECT
          vm.fish_code,
          vm.transgene_base_code || '(' || vm.allele_name || ')' AS g_expr
        FROM public.v_fish_main vm
        WHERE vm.allele_name IS NOT NULL AND vm.allele_name <> ''
      ) y
      GROUP BY y.fish_code
    )
    SELECT
      f.fish_code,
      f.nickname,
      f.dob                        AS birthday,
      COALESCE(f.genetic_background,'')  AS genetic_background,
      COALESCE(f.line_building_stage,'') AS line_building_stage,
      gp.genotype_pretty,
      mk.markers,
      COALESCE(r.fluors,'')        AS fluors,
      COALESCE(r.tags,'')          AS tags,
      COALESCE(r.dyes,'')          AS dyes,
      f.created_at
    FROM public.fish f
    LEFT JOIN gp ON gp.fish_code = f.fish_code
    LEFT JOIN mk ON mk.fish_code = f.fish_code
    LEFT JOIN public.v_fluorescent_marker_rollup r
      ON r.fish_code = f.fish_code
    WHERE (:q IS NULL)
       OR (
            f.fish_code ILIKE :q
         OR COALESCE(f.nickname,'')            ILIKE :q
         OR COALESCE(f.genetic_background,'')  ILIKE :q
         OR COALESCE(f.line_building_stage,'') ILIKE :q
         OR COALESCE(gp.genotype_pretty,'')    ILIKE :q
         OR COALESCE(mk.markers,'')            ILIKE :q
         OR COALESCE(r.fluors,'')              ILIKE :q
         OR COALESCE(r.tags,'')                ILIKE :q
         OR COALESCE(r.dyes,'')                ILIKE :q
         )
    ORDER BY f.created_at DESC NULLS LAST, f.fish_code
    LIMIT :lim
    """)
    params = {"q": (f"%{q}%" if q else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)

def _load_fish_rich_all(q: Optional[str], limit: int) -> pd.DataFrame:
    """
    Wider fallback: materialize per-allele rows from v_fish_main with base markers.
    """
    sql = text("""
      SELECT
        vm.fish_code,
        vm.transgene_base_code,
        vm.allele_number,
        vm.allele_name,
        vm.allele_nickname,
        vm.transgene_pretty_nickname,
        vm.transgene_pretty_name,
        vm.genotype_pretty,
        COALESCE(rb.fluors,'') AS base_fluors,
        COALESCE(rb.tags,'')   AS base_tags
      FROM public.v_fish_main vm
      LEFT JOIN public.v_fluorescent_marker_rollup_by_base rb
        ON rb.fish_code = vm.fish_code
       AND rb.ft_code   = vm.transgene_base_code
      WHERE (:q IS NULL)
         OR (
              vm.fish_code ILIKE :q
           OR vm.transgene_base_code ILIKE :q
           OR COALESCE(vm.allele_name,'') ILIKE :q
           OR COALESCE(vm.allele_nickname,'') ILIKE :q
           OR COALESCE(vm.genotype_pretty,'') ILIKE :q
         )
      ORDER BY vm.fish_code, vm.transgene_base_code, vm.allele_number
      LIMIT :lim
    """)
    params = {"q": (f"%{q}%" if q else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)

def _load_tanks_for_codes(codes: List[str]) -> pd.DataFrame:
    """
    Tanks for selected fish.
    v_tanks doesn't expose fish_code, so parse it from tank_code "TANK(<code>)#N".
    """
    if not codes:
        return pd.DataFrame(columns=["fish_code","tank_code","status","created_at","container_id"])
    sql = text(r"""
      SELECT
        v.tank_uuid::text         AS container_id,
        v.tank_code::text         AS tank_code,
        ''::text                  AS status,  -- no status column; blank for now
        regexp_replace(v.tank_code, '^.*\(([^)]+)\).*$', '\1')::text AS fish_code,
        v.created_at::timestamptz AS created_at
      FROM public.v_tanks v
      WHERE regexp_replace(v.tank_code, '^.*\(([^)]+)\).*$', '\1') = ANY(:codes)
      ORDER BY v.created_at ASC, v.tank_code ASC
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    return _coerce_strings(df)

def _fetch_enriched_for_containers(container_ids: List[str]) -> pd.DataFrame:
    """
    Enrich tank rows with fish nickname / genotype using fish + v_fish_main.
    """
    want_cols = [
        "container_id","label","status","fish_code",
        "nickname","name","alias","tank_display",
        "genotype","transgene_pretty",
        "genetic_background","stage","dob","tank_code"
    ]
    ids = [x for x in (container_ids or []) if x]
    if not ids:
        return pd.DataFrame(columns=want_cols)

    sql = text(r"""
  WITH picked AS (
    SELECT unnest(cast(:ids AS uuid[])) AS container_id
  ),
  vt AS (
    SELECT
        v.tank_uuid::uuid         AS tank_id,
        regexp_replace(v.tank_code, '^.*\(([^)]+)\).*$', '\1')::text AS fish_code,
        v.tank_code::text         AS tank_code,
        ''::text                  AS status,
        v.created_at::timestamptz AS created_at,
        split_part(v.tank_code, '#', 2)   AS tank_num
    FROM public.v_tanks v
  ),
  vf AS (
    SELECT
        f.fish_code::text                  AS fish_code,
        COALESCE(f.nickname,'')            AS nickname,
        COALESCE(f.genetic_background,'')  AS genetic_background,
        COALESCE(f.line_building_stage,'') AS stage,
        f.dob::date                        AS dob,
        -- use v_fish_main genotype_pretty (any row per fish)
        MAX(vm.genotype_pretty)            AS genotype,
        MAX(vm.genotype_pretty)            AS transgene_pretty
    FROM public.fish f
    LEFT JOIN public.v_fish_main vm
      ON vm.fish_code = f.fish_code
    GROUP BY f.fish_code, f.nickname, f.genetic_background, f.line_building_stage, f.dob
  )
  SELECT
    p.container_id::text                AS container_id,
    vt.tank_code                        AS tank_code,
    vt.status                           AS status,
    vt.fish_code                        AS fish_code,
    vf.nickname                         AS name_short,
    vf.nickname                         AS name,
    vf.nickname                         AS nickname,
    ''::text                            AS alias,
    CASE
      WHEN vt.tank_num IS NOT NULL AND vt.tank_num <> ''
        THEN 'TANK(' || vt.fish_code || ')#' || vt.tank_num
      ELSE vt.tank_code
    END                                  AS tank_display,
    vf.genotype                          AS genotype,
    vf.transgene_pretty                  AS transgene_pretty,
    vf.genetic_background                AS genetic_background,
    vf.stage                             AS stage,
    vf.dob                               AS dob
  FROM picked p
  JOIN vt  ON vt.tank_id = p.container_id
  LEFT JOIN vf ON vf.fish_code = vt.fish_code
  ORDER BY vt.created_at ASC, vt.tank_code ASC
""")
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": container_ids})

    if df.empty:
        return df
    for c in ["label","fish_code","genotype","transgene_pretty","genetic_background","stage","status","tank_display","tank_code","nickname","name"]:
        if c in df.columns:
            df[c] = df[c].fillna("")
    if "dob" in df.columns:
        try:
            df["dob"] = pd.to_datetime(df["dob"], errors="coerce").dt.date
        except Exception:
            df["dob"] = None
    return df[[c for c in want_cols if c in df.columns]]

# ─────────────────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────────────────
def main():
    st.title("🔎 Search Fish → Tanks")
    st.caption(f"DB_URL = {os.getenv('DB_URL','')}")

    with st.form("filters", clear_on_submit=False):
        c1, c2 = st.columns([3,1])
        with c1:
            q_raw = st.text_input("Search (code/nickname/background/genotype/alleles/fluors/tags)", "")
        with c2:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        _ = st.form_submit_button("Search")

    q = _normalize_q(q_raw)

    df = _load_fish_overview(q, limit)
    if df.empty:
        st.info("No fish match your search.")
        with st.expander("Advanced: per-allele rows (v_fish_main)"):
            raw = _load_fish_rich_all(q, limit)
            st.caption(f"{len(raw)} row(s) • columns: {', '.join(raw.columns)}")
            if not raw.empty:
                st.dataframe(raw, use_container_width=True, hide_index=True)
                st.download_button(
                    "⬇︎ Download v_fish_main_per_allele.csv",
                    data=raw.to_csv(index=False).encode("utf-8"),
                    file_name=f"v_fish_main_per_allele_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
                    type="secondary",
                    mime="text/csv"
                )
        return

    # Rename display headers
    df = df.rename(columns={
        "fish_code":          "Fish code",
        "nickname":           "Nickname",
        "birthday":           "Birth date",
        "genetic_background": "Genetic background",
        "line_building_stage":"Line-building stage",
        "genotype_pretty":    "Genotype",
        "markers":            "Markers",
        "fluors":             "Fluors",
        "tags":               "Tags",
        "dyes":               "Dyes",
        "created_at":         "Created time",
    })

    cols = [
        "Fish code","Nickname","Genetic background","Line-building stage",
        "Genotype","Markers","Fluors","Tags","Dyes","Birth date","Created time",
    ]
    cols = [c for c in cols if c in df.columns]

    st.subheader(f"Fish ({len(df)} rows)")
    table = df[cols].copy()
    table.insert(0, "✓ Select", False)

    editor_cols = ["✓ Select"] + cols
    fish_table = st.data_editor(
        table,
        hide_index=True,
        use_container_width=True,
        column_config=None,
        column_order=editor_cols,
        key="fish_table_v6",
    )

    # Tanks for selected fish
    st.subheader("Tanks for selected fish")

    selected_codes = (
        fish_table.loc[fish_table["✓ Select"], "Fish code"].dropna().astype(str).tolist()
        if isinstance(fish_table, pd.DataFrame) and "✓ Select" in fish_table.columns and "Fish code" in fish_table.columns
        else []
    )
    if not selected_codes:
        st.info("Select one or more fish to show their tanks.")
        st.stop()

    tdf = _load_tanks_for_codes(selected_codes)
    if tdf.empty:
        st.info("No tanks for selected fish.")
        st.stop()

    tcols = [c for c in ["fish_code","tank_code","status","created_at","container_id"] if c in tdf.columns]
    tview = tdf[tcols].copy()
    tview.insert(0, "✓ Print", False)

    tanks_table = st.data_editor(
        tview,
        use_container_width=True,
        hide_index=True,
        column_order=["✓ Print"] + tcols,
        key="tank_table",
    )

    chosen = (
        tanks_table.loc[tanks_table["✓ Print"] == True]
        if isinstance(tanks_table, pd.DataFrame) and "✓ Print" in tanks_table.columns
        else pd.DataFrame()
    )

    st.caption(f"{len(chosen)} tank(s) selected for labels)")

    if chosen.empty:
        st.stop()

    ids = chosen["container_id"].astype(str).tolist()
    edf = _fetch_enriched_for_containers(ids)

    if edf is None or edf.empty:
        st.info("No enriched tank data to print.")
        st.stop()

    rows = []
    for _, r in edf.iterrows():
        name = (r.get("name") or "").strip()
        nick = (r.get("nickname") or "").strip()
        if name and nick and name.lower() == nick.lower():
            nick = ""
        rows.append({
            "label":              (name or r.get("fish_code") or r.get("tank_code")),
            "nickname":           nick,
            "name":               name,
            "alias":              r.get("alias") or "",
            "tank_display":       r.get("tank_display") or "",
            "tank_code":          r.get("tank_code") or "",
            "genotype":           r.get("genotype", ""),
            "genetic_background": r.get("genetic_background") or "",
            "stage":              r.get("stage") or "",
            "dob":                r.get("dob"),
            "fish_code":          r.get("fish_code") or "",
        })

    from carp_app.ui.lib.labels_components import build_tank_labels_pdf
    pdf_bytes = build_tank_labels_pdf(rows) if rows else b""
    st.download_button(
        "⬇︎ Download PDF labels (2.4×1.5 • QR)",
        data=pdf_bytes,
        file_name=f"tank_labels_2_4x1_5_{utc_now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
        disabled=(pdf_bytes == b""),
    )

if __name__ == "__main__":
    main()