from lib.page_bootstrap import secure_page; secure_page()

import pandas as pd
import streamlit as st
from sqlalchemy import text

from lib_shared import parse_query
from lib.authz import require_app_access, logout_button
from lib import db as _dbmod
from lib.db import get_engine, fetch_df, quick_db_check

# Optional health panel
try:
    from health import render_health_panel
except Exception:
    def render_health_panel(_engine):
        pass

# ---- Page setup & access ----
st.set_page_config(page_title="Fish Overview", layout="wide")
require_app_access("🔐 CARP — Private")
logout_button("sidebar", key="logout_btn_overview")  # unique key

# ---- DB engine & quick diagnostics ----
_engine = get_engine()  # honors secrets/env incl. sslmode
st.caption(f"DB DSN: {_dbmod._dsn_from_secrets()}")
st.caption(quick_db_check(_engine))
render_health_panel(_engine)

# ---- Helpers ---------------------------------------------------------------
def has_col(cx, table: str, col: str) -> bool:
    q = text("""
        SELECT EXISTS (
          SELECT 1 FROM information_schema.columns
          WHERE table_schema='public' AND table_name=:tbl AND column_name=:col
        );
    """)
    return bool(cx.execute(q, {"tbl": table, "col": col}).scalar())

def detect_tank_sql(cx):
    tbl_exists = text("""
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema='public' AND table_name=:t
        );
    """)
    if cx.execute(tbl_exists, {"t": "tank_assignments"}).scalar():
        return {"select": "ta.tank_label AS tank", "join": "LEFT JOIN public.tank_assignments ta ON ta.fish_id = f.id"}
    if has_col(cx, "fish", "tank"):
        return {"select": "f.tank AS tank", "join": ""}
    if has_col(cx, "fish", "tank_label"):
        return {"select": "f.tank_label AS tank", "join": ""}

    has_ft = cx.execute(tbl_exists, {"t": "fish_tanks"}).scalar()
    has_t  = cx.execute(tbl_exists, {"t": "tanks"}).scalar()
    if has_ft and has_t:
        name_ok  = has_col(cx, "tanks", "name")
        label_ok = has_col(cx, "tanks", "label")
        tank_expr = "t.name" if name_ok else ("t.label" if label_ok else "NULL")
        type_q = text("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=:tbl AND column_name=:col
        """)
        ft_tid = cx.execute(type_q, {"tbl":"fish_tanks","col":"tank_id"}).scalar()
        t_id   = cx.execute(type_q, {"tbl":"tanks","col":"id"}).scalar()
        join_expr = "t.id = ft.tank_id" if (ft_tid == t_id) else "t.id::text = ft.tank_id::text"
        return {"select": f"COALESCE({tank_expr}, '') AS tank",
                "join": ("LEFT JOIN public.fish_tanks ft ON ft.fish_id = f.id "
                         f"LEFT JOIN public.tanks t ON {join_expr}")}

    return {"select": "'' AS tank", "join": ""}

# ---- Search (AND/OR, quotes) -----------------------------------------------
st.caption('Global search supports **AND/OR** and quoted phrases, e.g. `fish-201 AND "gcamp"`')
q = st.text_input("Global search", value="")
q_parsed = parse_query(q)
mode = q_parsed["mode"]
terms = q_parsed["terms"]

where_clauses = []
params = {}
if terms:
    bundles = []
    for i, term in enumerate(terms):
        k = f"t{i}"
        params[k] = f"%{term}%"
        bundles.append(
            "("
            f"f.name ILIKE :{k} OR "
            f"f.auto_fish_code ILIKE :{k} OR "
            f"coalesce(f.nickname,'') ILIKE :{k} OR "
            f"coalesce(f.strain,'') ILIKE :{k} OR "
            f"coalesce(f.description,'') ILIKE :{k} OR "
            f"coalesce(tg.transgene_names,'') ILIKE :{k} OR "
            f"coalesce(tg.transgene_codes,'') ILIKE :{k}"
            ")"
        )
    joiner = " AND " if mode == "AND" else " OR "
    where_clauses.append("(" + joiner.join(bundles) + ")")

where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

# ---- Main query -------------------------------------------------------------
with _engine.connect() as cx:
    tank = detect_tank_sql(cx)

    has_nick = has_col(cx, "fish", "nickname")
    has_dob  = has_col(cx, "fish", "date_of_birth")
    nick_sel = "f.nickname" if has_nick else "NULL::text"
    dob_sel  = "f.date_of_birth" if has_dob else "NULL::date"

    has_tgn_name = has_col(cx, "transgenes", "name")
    name_expr = "COALESCE(NULLIF(t.name,''), t.transgene_base_code)" if has_tgn_name else "t.transgene_base_code"

    auto_code_expr = (
        "f.auto_fish_code" if has_col(cx, "fish", "auto_fish_code")
        else ("f.fish_code" if has_col(cx, "fish", "fish_code")
        else ("f.auto_code" if has_col(cx, "fish", "auto_code")
        else "NULL::text"))
    )

    sql = f"""
    WITH tg AS (
      SELECT
        fta.fish_id,
        string_agg(DISTINCT t.transgene_base_code, ', ' ORDER BY t.transgene_base_code) AS transgene_codes,
        string_agg(DISTINCT {name_expr}, ', ' ORDER BY {name_expr}) AS transgene_names
      FROM public.fish_transgene_alleles fta
      JOIN public.transgenes t
        ON t.transgene_base_code = fta.transgene_base_code
      GROUP BY fta.fish_id
    ),
    alle AS (
      SELECT
        x.fish_id,
        string_agg(DISTINCT x.allele_label, ', ' ORDER BY x.allele_label) AS alleles
      FROM (
        SELECT
          f.id AS fish_id,
          trim(
            CONCAT(
              fta.transgene_base_code,
              CASE WHEN NULLIF(fta.allele_number,'') IS NOT NULL
                   THEN '('||fta.allele_number||')'
                   ELSE ''
              END
            )
          ) AS allele_label
        FROM public.fish f
        LEFT JOIN public.fish_transgene_alleles fta
          ON fta.fish_id = f.id
      ) x
      GROUP BY x.fish_id
    ),
    tx AS (
      SELECT ft.fish_id,
             count(DISTINCT ft.treatment_id) AS n_treatments,
             max(t.performed_at)::date       AS last_treatment_on
      FROM public.fish_treatments ft
      JOIN public.treatments t ON t.id = ft.treatment_id
      GROUP BY ft.fish_id
    )
    SELECT
      f.name                             AS fish_name,
      {auto_code_expr}                   AS auto_fish_code,
      f.batch_label                      AS batch,
      f.line_building_stage              AS line_building_stage,
      {nick_sel}                         AS nickname,
      {dob_sel}                          AS date_of_birth,
      f.description                      AS description,
      {tank['select']},
      COALESCE(tg.transgene_names, '')   AS transgenes,
      COALESCE(alle.alleles, '')         AS alleles,
      COALESCE(tx.n_treatments, 0)       AS n_treatments,
      tx.last_treatment_on
    FROM public.fish f
    LEFT JOIN tg   ON tg.fish_id   = f.id
    LEFT JOIN alle ON alle.fish_id = f.id
    LEFT JOIN tx   ON tx.fish_id   = f.id
    {tank['join']}
    {where_sql}
    ORDER BY fish_name
    LIMIT :lim;
    """

    params["lim"] = 5000
    df = pd.read_sql(text(sql), cx, params=params)

# ---- Display ---------------------------------------------------------------
st.title("Fish Overview")

if df.empty:
    st.info("No fish found.")
else:
    show_cols = [
        "fish_name",
        "nickname",
        "auto_fish_code",
        "batch",
        "line_building_stage",
        "date_of_birth",
        "tank",
        "transgenes",
        "alleles",
        "description",
        "n_treatments",
        "last_treatment_on",
    ]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols], hide_index=True, width="stretch")

    st.download_button(
        "Download CSV",
        df[show_cols].to_csv(index=False).encode("utf-8"),
        file_name="fish_overview.csv",
        mime="text/csv",
    )

# Optional: small rollup sample from the view if present
st.subheader("Fish overview (first 50 from v_fish_overview_v1, if available)")
try:
    with _engine.connect() as cx:
        df2 = fetch_df(cx, "select * from public.v_fish_overview_v1 order by fish_name nulls last limit 50")
    st.dataframe(df2, width="stretch")
except Exception as e:
    st.info(f"Rollup view not available yet: {e}")
