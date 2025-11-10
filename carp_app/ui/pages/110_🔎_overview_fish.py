# carp_app/ui/pages/110_🔎_overview_fish.py
from __future__ import annotations
import sys, pathlib, os
from typing import Optional, List
import pandas as pd
import streamlit as st
from sqlalchemy import text, bindparam
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import ARRAY, UUID

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

# ───────────────────────────────── helpers ──────────────────────────────────
def _normalize_q(q_raw: str) -> Optional[str]:
    q = (q_raw or "").strip()
    return q or None

def _coerce_strings(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _table_exists(schema: str, table: str) -> bool:
    sql = text("""
      SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema=:s AND table_name=:t
      )
    """)
    with _get_engine().begin() as cx:
        return bool(cx.execute(sql, {"s": schema, "t": table}).scalar())

# ───────────────────────────── data loaders ────────────────────────────────
def _load_fish_overview(q: Optional[str], limit: int) -> pd.DataFrame:
    sql = text("""
      SELECT
        fish_code_display,
        fish_code_raw,
        nickname,
        birthday,
        genetic_background,
        line_building_stage,
        genotype_pretty,
        markers,
        fluors,
        tags,
        fusions,
        n_fusions,
        dyes,
        created_at
      FROM public.v_fish_overview v
      WHERE (:q IS NULL)
         OR (
              v.fish_code_raw       ILIKE :q
           OR v.fish_code_display   ILIKE :q
           OR v.nickname            ILIKE :q
           OR v.genetic_background  ILIKE :q
           OR v.line_building_stage ILIKE :q
           OR v.genotype_pretty     ILIKE :q
           OR v.markers             ILIKE :q
           OR v.fluors              ILIKE :q
           OR v.tags                ILIKE :q
           OR v.fusions             ILIKE :q
         )
      ORDER BY v.created_at DESC NULLS LAST, v.fish_code_raw
      LIMIT :lim
    """)
    params = {"q": (f"%{q}%" if q else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)

def _load_fish_rich_all(q: Optional[str], limit: int) -> pd.DataFrame:
    has_fp = _table_exists("public", "ft_proteins")
    if has_fp:
        rb_cte = """
        rb AS (
          SELECT
            f.fish_code,
            jff.ft_code AS transgene_base_code,
            COALESCE(string_agg(DISTINCT fp.fluor_code, ','), '')          AS base_fluors,
            COALESCE(string_agg(DISTINCT NULLIF(fp.tag_code,''), ','), '') AS base_tags
          FROM public.fish f
          LEFT JOIN public.join_fish_fluorescent_treatments jff
            ON jff.fish_id = f.id
          LEFT JOIN public.ft_proteins fp
            ON fp.ft_code = jff.ft_code
          GROUP BY f.fish_code, jff.ft_code
        )
        """
    else:
        rb_cte = """
        rb AS (
          SELECT
            f.fish_code,
            jff.ft_code AS transgene_base_code,
            ''::text AS base_fluors,
            ''::text AS base_tags
          FROM public.fish f
          LEFT JOIN public.join_fish_fluorescent_treatments jff
            ON jff.fish_id = f.id
          GROUP BY f.fish_code, jff.ft_code
        )
        """

    sql = text(f"""
      WITH jt AS (
        SELECT
          f.fish_code,
          jfta.transgene_base_code,
          jfta.allele_number,
          ta.allele_name,
          ta.allele_nickname
        FROM public.join_fish_transgene_alleles jfta
        JOIN public.fish f
          ON f.id = jfta.fish_id
        LEFT JOIN public.transgene_alleles ta
          ON ta.transgene_base_code = jfta.transgene_base_code
         AND ta.allele_number       = jfta.allele_number
      ),
      {rb_cte}
      SELECT
        jt.fish_code,
        jt.transgene_base_code,
        jt.allele_number,
        COALESCE(jt.allele_name,'')      AS allele_name,
        COALESCE(jt.allele_nickname,'')  AS allele_nickname,
        ''::text AS transgene_pretty_nickname,
        ''::text AS transgene_pretty_name,
        ''::text AS genotype_pretty,
        COALESCE(rb.base_fluors,'') AS base_fluors,
        COALESCE(rb.base_tags,'')   AS base_tags
      FROM jt
      LEFT JOIN rb
        ON rb.fish_code = jt.fish_code
       AND rb.transgene_base_code = jt.transgene_base_code
      WHERE (:q IS NULL)
         OR (
              jt.fish_code ILIKE :q
           OR jt.transgene_base_code ILIKE :q
           OR COALESCE(jt.allele_name,'') ILIKE :q
           OR COALESCE(jt.allele_nickname,'') ILIKE :q
         )
      ORDER BY jt.fish_code, jt.transgene_base_code, jt.allele_number
      LIMIT :lim
    """)
    params = {"q": (f"%{q}%" if q else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)

def _fetch_enriched_for_containers(container_ids: List[str]) -> pd.DataFrame:
    want_cols = [
        "container_id","label","status","fish_code",
        "nickname","name","alias","tank_display",
        "genotype","transgene_pretty",
        "genetic_background","stage","dob","tank_code"
    ]
    ids = [x for x in (container_ids or []) if x]
    if not ids:
        return pd.DataFrame(columns=want_cols)

    use_view = _table_exists("public", "v_tanks")
    src_table = "public.v_tanks" if use_view else "public.tanks"
    id_col   = "tank_uuid" if use_view else "id"

    sql = text(f"""
  WITH picked AS (
    SELECT unnest(:ids) AS container_id
  ),
  vt AS (
    SELECT
        v.{id_col}::uuid                              AS tank_id,
        regexp_replace(v.tank_code, '^.*\\(([^)]+)\\).*$', '\\1')::text AS fish_code,
        v.tank_code::text                             AS tank_code,
        COALESCE(CAST(v.status AS text), ''::text)    AS status,
        v.created_at::timestamptz                     AS created_at,
        split_part(v.tank_code, '#', 2)               AS tank_num
    FROM {src_table} v
  ),
  gp AS (
    SELECT
      f.fish_code,
      string_agg(
        DISTINCT (ta.transgene_base_code || '(' || ta.allele_name || ')'),
        ', ' ORDER BY (ta.transgene_base_code || '(' || ta.allele_name || ')')
      ) AS genotype
    FROM public.fish f
    LEFT JOIN public.join_fish_transgene_alleles jfta
      ON jfta.fish_id = f.id
    LEFT JOIN public.transgene_alleles ta
      ON ta.transgene_base_code = jfta.transgene_base_code
     AND ta.allele_number       = jfta.allele_number
    WHERE COALESCE(ta.allele_name,'') <> ''
    GROUP BY f.fish_code
  ),
  vf AS (
    SELECT
        f.fish_code::text                  AS fish_code,
        COALESCE(f.nickname,'')            AS nickname,
        COALESCE(f.genetic_background,'')  AS genetic_background,
        COALESCE(f.in_breeding_stage,'')   AS stage,
        f.birthday::date                   AS dob,
        COALESCE(gp.genotype,'')           AS genotype,
        COALESCE(gp.genotype,'')           AS transgene_pretty
    FROM public.fish f
    LEFT JOIN gp
      ON gp.fish_code = f.fish_code
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
    vf.birthday                          AS dob
  FROM picked p
  JOIN vt  ON vt.tank_id = p.container_id
  LEFT JOIN vf ON vf.fish_code = vt.fish_code
  ORDER BY vt.created_at ASC, vt.tank_code ASC
""").bindparams(bindparam("ids", type_=ARRAY(UUID(as_uuid=True))))
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": ids})
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
    want = [c for c in want_cols if c in df.columns]
    return df[want]

def _load_tanks_for_codes(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=["fish_code","tank_code","status","created_at","container_id"])

    use_view = _table_exists("public", "v_tanks")
    src_table = "public.v_tanks" if use_view else "public.tanks"
    id_col   = "tank_uuid" if use_view else "id"

    sql = text(f"""
      SELECT
        v.{id_col}::text                                           AS container_id,
        v.tank_code::text                                          AS tank_code,
        COALESCE(CAST(v.status AS text), ''::text)                 AS status,
        regexp_replace(v.tank_code, '^.*\\(([^)]+)\\).*$', '\\1')::text AS fish_code,
        v.created_at::timestamptz                                  AS created_at
      FROM {src_table} v
      WHERE regexp_replace(v.tank_code, '^.*\\(([^)]+)\\).*$', '\\1') = ANY(:codes)
      ORDER BY v.created_at ASC, v.tank_code ASC
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    return _coerce_strings(df)

# ───────────────────────────────── page ──────────────────────────────────────
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
        with st.expander("Advanced: per-allele rows (direct from base tables)"):
            raw = _load_fish_rich_all(q, limit)
            st.caption(f"{len(raw)} row(s) • columns: {', '.join(raw.columns)}")
            if not raw.empty:
                st.dataframe(raw, width="stretch", hide_index=True)
                st.download_button(
                    "⬇︎ Download per_allele.csv",
                    data=raw.to_csv(index=False).encode("utf-8"),
                    file_name=f"per_allele_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
                    type="secondary",
                    mime="text/csv",
                    width="stretch",
                )
        return

    df = df.rename(columns={
        "fish_code_display":   "Fish code",
        "nickname":            "Nickname",
        "birthday":            "Birth date",
        "genetic_background":  "Genetic background",
        "line_building_stage": "Line-building stage",
        "genotype_pretty":     "Genotype",
        "markers":             "Markers",
        "fluors":              "Fluors",
        "tags":                "Tags",
        "fusions":             "Fusions",
        "n_fusions":           "# Fusions",
        "dyes":                "Dyes",
        "created_at":          "Created time",
    })

    cols = [
        "Fish code","Nickname","Genetic background","Line-building stage",
        "Genotype","Markers","Fluors","Tags","Fusions","# Fusions","Dyes",
        "Birth date","Created time",
    ]
    cols = [c for c in cols if c in df.columns]

    st.subheader(f"Fish ({len(df)} rows)")
    table = df[cols].copy()
    table.insert(0, "✓ Select", False)

    fish_table = st.data_editor(
        table,
        hide_index=True,
        width="stretch",
        column_config=None,
        column_order=["✓ Select"] + cols,
        key="fish_table_v7",
    )

    st.subheader("Tanks for selected fish")

    selected_codes = (
        fish_table.loc[fish_table["✓ Select"], "Fish code"].dropna().astype(str).tolist()
        if isinstance(fish_table, pd.DataFrame) and "✓ Select" in fish_table.columns and "Fish code" in fish_table.columns
        else []
    )
    if selected_codes:
        disp_to_raw = dict(zip(df["Fish code"], df.get("fish_code_raw", df["Fish code"])))
        selected_codes = [disp_to_raw.get(c, c) for c in selected_codes]

    tdf = _load_tanks_for_codes(selected_codes)
    if tdf.empty:
        st.info("No tanks for selected fish.")
        st.stop()

    tcols = [c for c in ["fish_code","tank_code","status","created_at","container_id"] if c in tdf.columns]
    tview = tdf[tcols].copy()
    tview.insert(0, "✓ Print", False)

    tanks_table = st.data_editor(
        tview,
        width="stretch",
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
        width="stretch",
        disabled=(pdf_bytes == b""),
    )

if __name__ == "__main__":
    main()