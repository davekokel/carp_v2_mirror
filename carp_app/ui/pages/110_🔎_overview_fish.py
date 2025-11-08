from __future__ import annotations
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── app libs / auth ──────────────────────────────────────────────────────────
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

# ── std/3p ───────────────────────────────────────────────────────────────────
import os
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── app libs ─────────────────────────────────────────────────────────────────
from carp_app.ui.lib.app_ctx import get_engine as _create_engine
from carp_app.ui.lib.labels_components import build_tank_labels_pdf  # 2.4"×1.5" + QR

# ─────────────────────────────────────────────────────────────────────────────
# Engine (cached)
# ─────────────────────────────────────────────────────────────────────────────
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
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _load_fish_rich_all(q: str | None, limit: int) -> pd.DataFrame:
    """
    Fallback: return a wider/raw view of fish when the summary query is empty.
    Uses the same filter as _load_fish_overview but selects all columns from v_fish_overview_id.
    """
    sql = text("""
        SELECT *
        FROM public.v_fish_unified
        WHERE (:q IS NULL)
            OR (
                fish_code ILIKE :q
            OR COALESCE(nickname,'')            ILIKE :q
            OR COALESCE(genetic_background,'')  ILIKE :q
            OR COALESCE(line_building_stage,'') ILIKE :q
            OR COALESCE(genotype_pretty,'')     ILIKE :q
            OR COALESCE(markers,'')             ILIKE :q
            OR COALESCE(fluors,'')              ILIKE :q
            OR COALESCE(tags,'')                ILIKE :q
            OR COALESCE(dyes,'')                ILIKE :q
            )
        ORDER BY created_at DESC NULLS LAST, fish_code
        LIMIT :lim
        """)
    params = {"q": (f"%{q}%" if q else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)

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
      SELECT
        fish_code, nickname, birthday, genetic_background, line_building_stage,
        genotype_pretty,
        markers,        -- base(allele) codes
        fluors, tags, dyes,
        created_at
      FROM public.v_fish_unified
      WHERE (:q IS NULL)
         OR (
              fish_code ILIKE :q
           OR COALESCE(nickname,'')            ILIKE :q
           OR COALESCE(genetic_background,'')  ILIKE :q
           OR COALESCE(line_building_stage,'') ILIKE :q
           OR COALESCE(genotype_pretty,'')     ILIKE :q
           OR COALESCE(markers,'')             ILIKE :q
           OR COALESCE(fluors,'')              ILIKE :q
           OR COALESCE(tags,'')                ILIKE :q
           OR COALESCE(dyes,'')                ILIKE :q
         )
      ORDER BY created_at DESC NULLS LAST, fish_code
      LIMIT :lim
    """)
    params = {"q": (f"%{q}%" if q else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)   # <-- add this

def _load_tanks_for_codes(codes: list[str]) -> pd.DataFrame:
    """
    v_tanks in this schema does not expose fish_code → parse it from tank_code "TANK(<code>)#N".
    """
    if not codes:
        return pd.DataFrame(columns=["fish_code","tank_code","status","created_at","container_id"])
    sql = text(r"""
      SELECT
        v.tank_uuid::text         AS container_id,
        v.tank_code::text         AS tank_code,
        ''::text                  AS status,  -- v_tanks has no status; display blank (or 'active')
        regexp_replace(v.tank_code, '^.*\(([^)]+)\).*$', '\1')::text AS fish_code,
        v.created_at::timestamptz AS created_at
      FROM public.v_tanks v
      WHERE regexp_replace(v.tank_code, '^.*\(([^)]+)\).*$', '\1') = ANY(:codes)
      ORDER BY v.created_at ASC, v.tank_code ASC
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    return _coerce_strings(df)

def _fetch_enriched_for_containers(container_ids: list[str]) -> pd.DataFrame:
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
        f.birthday::date                   AS dob,
        COALESCE(f.genotype_pretty,'')     AS genotype,
        COALESCE(f.genotype_pretty,'')     AS transgene_pretty
    FROM public.v_fish_unified f
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
            q_raw = st.text_input("Search (code/name/nickname/background/transgene/genotype/alleles/fluors/fusions/tags)", "")
        with c2:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        _ = st.form_submit_button("Search")

    q = (q_raw or "").strip() or None

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

    # Rename display headers (match v_fish_overview_id)
    df = df.rename(columns={
        "fish_code":          "fish_code",
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

    show_cols = [
        "fish_code","Nickname","Genetic background","Line-building stage",
        "Genotype","Markers","Fluors","Tags","Dyes",
        "Birth date","Created time",
    ]
    show_cols = [c for c in show_cols if c in df.columns]
    st.subheader(f"Fish ({len(df)} rows)")

    table = df[show_cols].copy()
    table.insert(0, "✓ Select", False)

    editor_cols = ["✓ Select"] + show_cols
    fish_table = st.data_editor(
        table,
        hide_index=True,
        use_container_width=True,
        column_config=None,
        column_order=editor_cols,
        key="fish_table_v4",
    )

    # Tanks for selected fish
    st.subheader("Tanks for selected fish")

    selected_codes = (
        fish_table.loc[fish_table["✓ Select"], "fish_code"].dropna().astype(str).tolist()
        if isinstance(fish_table, pd.DataFrame) and "✓ Select" in fish_table.columns and "fish_code" in fish_table.columns
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
    tview.insert(0, "✓ Print", False)  # make the Print selector the first column

    tanks_table = st.data_editor(
        tview,
        use_container_width=True,
        hide_index=True,
        column_order=["✓ Print"] + tcols,  # ensure first column
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