# carp_app/ui/pages/009_📤_upload_plasmids_single.py
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

import io, os
from typing import Optional
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from carp_app.ui.lib.app_ctx import get_engine

PAGE_TITLE = "📤 Upload Plasmids — single format (upsert + link fusions)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)
st.caption(
    "Format: one CSV/XLSX with plasmid fields and fusion fields. "
    "Multiple fusions per plasmid are separated by `;` or `|`. "
    "Within each fusion use `tag::fluor` (back-compat `tag+fluor`). "
    "Humans provide **nickname** only — the DB generates the canonical `name`."
)

# ---------------------------------------------------------------------------
# Example template (nickname only; no 'name')
# ---------------------------------------------------------------------------
def _example_bytes_name_mime():
    cols = [
        "code","nickname","resistance","supports_invitro_rna","notes",
        "tag_description",
        "fusion_name","fluor_name","tag_name",
    ]
    sample = pd.DataFrame([
        {"code":"pEX001","nickname":"ex1","resistance":"Amp","supports_invitro_rna":True,"notes":"columns win","tag_description":"Mito anchor","fluor_name":"mStayGold","tag_name":"2Xcox8A"},
        {"code":"pEX002","nickname":"ex2","resistance":"Kan","supports_invitro_rna":False,"notes":"multi via fusion_name","tag_description":"ER anchor","fusion_name":"2Xcox8A::mStayGold; sec61b::mChilada"},
        {"code":"pEX003","nickname":"ex3","resistance":"Amp","supports_invitro_rna":True,"notes":"back-compat +","tag_description":"ER anchor","fusion_name":"sec61b+mChilada"},
    ], columns=cols)
    data = sample.to_csv(index=False).encode()
    return data, "plasmids_single_format_example.csv", "text/csv"

_data, _name, _mime = _example_bytes_name_mime()
st.download_button("⬇️ Download example — single format", data=_data, file_name=_name, mime=_mime, type="secondary", use_container_width=True)

# ---------------------------------------------------------------------------
# Engine / helpers
# ---------------------------------------------------------------------------
_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        if not os.getenv("DB_URL"):
            st.error("DB_URL not set"); st.stop()
        _ENGINE = get_engine()
    return _ENGINE

def _norm_bool(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return False
    return str(v).strip().lower() in {"1","true","t","yes","y"}

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
file = st.file_uploader("Upload single-format file (.csv or .xlsx)", type=["csv","xlsx"])
if not file:
    st.info("Choose a CSV/XLSX to begin.")
    st.stop()

try:
    if file.name.lower().endswith(".xlsx"):
        df_raw = pd.read_excel(io.BytesIO(file.read()), dtype=object)
    else:
        df_raw = pd.read_csv(file, dtype=object)
except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

df_raw.columns = [c.strip() for c in df_raw.columns]
st.subheader("Preview")
st.dataframe(df_raw.head(20), use_container_width=True, hide_index=True)
st.caption(f"{len(df_raw)} rows")

# ---------------------------------------------------------------------------
# One-button process: stage → upsert plasmids (nickname only) → link fusions
# ---------------------------------------------------------------------------
creator_uuid = getattr(user, "id", None)
created_by_uuid = str(creator_uuid) if creator_uuid else None

if st.button("Process upload (upsert plasmids + link fusions)", type="primary", use_container_width=True):
    # 1) Shape & stage into raw.plasmids_option1_full
    expected = [
        "plasmid_code","nickname","fluors","tag_description","resistance","notes","supports_invitro_rna",
        "fusion_name","fluor_name","tag_name"
    ]
    df_stage = df_raw.copy()
    alias_map = {"code": "plasmid_code"}  # legacy -> new
    for a, b in alias_map.items():
        if a in df_stage.columns and b not in df_stage.columns:
            df_stage[b] = df_stage[a]
    for c in expected:
        if c not in df_stage.columns:
            df_stage[c] = None

    with _eng().begin() as cx:
        cx.execute(text("create schema if not exists raw;"))
        cx.execute(text("""
            create table if not exists raw.plasmids_option1_full (
              plasmid_code text,
              nickname text,
              fluors text,
              tag_description text,
              resistance text,
              notes text,
              supports_invitro_rna text,
              fusion_name text,
              fluor_name text,
              tag_name text
            )
        """))
        cx.execute(text("truncate raw.plasmids_option1_full;"))

        df_stage = df_stage[expected]
        recs_raw = df_stage.where(pd.notna(df_stage), None).to_dict(orient="records")
        cx.execute(text("""
            insert into raw.plasmids_option1_full (
              plasmid_code, nickname, fluors, tag_description,
              resistance, notes, supports_invitro_rna,
              fusion_name, fluor_name, tag_name
            )
            values (
              :plasmid_code, :nickname, :fluors, :tag_description,
              :resistance, :notes, :supports_invitro_rna,
              :fusion_name, :fluor_name, :tag_name
            )
        """), recs_raw)

    # 2) Upsert public.plasmids (nickname only; name generated on insert)
    df_pl = pd.DataFrame({
        "code": df_stage["plasmid_code"].fillna("").map(str).str.strip(),
        "nickname": df_stage["nickname"],
        "resistance": df_stage["resistance"],
        "supports_invitro_rna": df_stage["supports_invitro_rna"].map(lambda v: str(v).strip().lower() in {"1","true","t","yes","y"}),
        "notes": df_stage["notes"],
        "created_by": created_by_uuid,
    })
    df_pl = df_pl[df_pl["code"] != ""].drop_duplicates(subset=["code"])
    # satisfy NOT NULL name on insert; do not overwrite on conflict
    df_pl["name"] = df_pl["nickname"].where(df_pl["nickname"].notna() & (df_pl["nickname"] != ""), df_pl["code"])
    recs_pl = df_pl.where(pd.notna(df_pl), None).to_dict(orient="records")

    with _eng().begin() as cx:
      cx.execute(text("""
          INSERT INTO public.plasmids (code, name, nickname, resistance, supports_invitro_rna, notes, created_by)
          VALUES (:code, :name, :nickname, :resistance, :supports_invitro_rna, :notes, :created_by)
          ON CONFLICT (code) DO UPDATE
            SET nickname            = EXCLUDED.nickname,
                resistance          = EXCLUDED.resistance,
                supports_invitro_rna= EXCLUDED.supports_invitro_rna,
                notes               = EXCLUDED.notes,
                created_by          = EXCLUDED.created_by
      """), recs_pl)

    # 3) Build catalogs and link fusions by IDs (no code-mode)
    dml_sql = r"""
WITH params AS (
  SELECT '[;|]'::text AS list_sep, '::|\\+'::text AS inner_sep
),
src AS (
  SELECT r.*,
         regexp_split_to_array(coalesce(nullif(fusion_name, ''), ''), (SELECT list_sep FROM params)) AS a_fus,
         regexp_split_to_array(coalesce(nullif(fluor_name,  ''), ''), (SELECT list_sep FROM params)) AS a_flu,
         regexp_split_to_array(coalesce(nullif(tag_name,    ''), ''), (SELECT list_sep FROM params)) AS a_tag
  FROM raw.plasmids_option1_full r
),
exploded AS (
  SELECT s.plasmid_code, g AS idx,
         nullif(coalesce(s.a_fus[least(g, nullif(array_length(s.a_fus, 1), 0))], ''), '') AS fusion_name_raw,
         nullif(coalesce(s.a_flu[least(g, nullif(array_length(s.a_flu, 1), 0))], ''), '') AS fluor_name_raw,
         nullif(coalesce(s.a_tag[least(g, nullif(array_length(s.a_tag, 1), 0))], ''), '') AS tag_name_raw
  FROM src s
  CROSS JOIN LATERAL generate_series(
    1, greatest(coalesce(array_length(s.a_fus, 1), 1),
                coalesce(array_length(s.a_flu, 1), 1),
                coalesce(array_length(s.a_tag, 1), 1))
  ) g
),
parsed AS (
  SELECT
    e.plasmid_code,
    NULLIF(trim(fusion_name_raw), '') AS fusion_name,
    NULLIF(
      trim(
        COALESCE(
          fluor_name_raw,
          (regexp_split_to_array(fusion_name_raw, (SELECT inner_sep FROM params)))[2]
        )
      ),
      ''
    ) AS fluor_name,
    NULLIF(
      trim(
        COALESCE(
          tag_name_raw,
          (regexp_split_to_array(fusion_name_raw, (SELECT inner_sep FROM params)))[1]
        )
      ),
      ''
    ) AS tag_name
  FROM exploded e
),
clean AS (
  SELECT
    LOWER(TRIM(p.plasmid_code)) AS plasmid_code,
    NULLIF(TRIM(p.fusion_name), '') AS fusion_name,
    NULLIF(LOWER(REGEXP_REPLACE(p.fluor_name, '[^A-Za-z0-9]+','-','g')), '') AS fluor_slug,
    NULLIF(LOWER(REGEXP_REPLACE(p.tag_name,   '[^A-Za-z0-9]+','-','g')),   '') AS tag_slug,
    p.fluor_name,
    p.tag_name
  FROM parsed p
),
clean_with_fluor AS (
  SELECT * FROM clean WHERE fluor_slug IS NOT NULL
),
tmp_fluors AS (
  SELECT DISTINCT
    'flu-'||fluor_slug AS fluor_code,
    MIN(fluor_name)    AS fluor_name
  FROM clean_with_fluor
  GROUP BY 1
),
tmp_tags AS (
  SELECT DISTINCT
    'tag-'||tag_slug AS tag_code,
    MIN(tag_name)    AS tag_name
  FROM clean_with_fluor
  WHERE tag_slug IS NOT NULL
  GROUP BY 1
),
tmp_fusions AS (
  SELECT DISTINCT
    'fus-'||
      LOWER(
        REGEXP_REPLACE(
          CONCAT_WS('--',
            COALESCE(fusion_name, CONCAT_WS(' + ', fluor_name, NULLIF(tag_name,''))),
            'flu-'||LOWER(fluor_slug),
            COALESCE(CASE WHEN tag_slug IS NOT NULL THEN 'tag-'||LOWER(tag_slug) END,'')
          ),
          '[^A-Za-z0-9]+','-','g'
        )
      ) AS fusion_code,
    COALESCE(fusion_name, CONCAT_WS(' + ', fluor_name, NULLIF(tag_name,''))) AS fusion_name_norm,
    'flu-'||LOWER(fluor_slug) AS fluor_code,
    CASE WHEN tag_slug IS NOT NULL THEN 'tag-'||LOWER(tag_slug) END AS tag_code
  FROM clean_with_fluor
),
map_fluor_ids AS (
  SELECT f.id AS fluor_id, t.fluor_code
  FROM tmp_fluors t
  JOIN public.fluors f ON f.fluor_code = t.fluor_code
),
map_tag_ids AS (
  SELECT tg.id AS tag_id, t.tag_code
  FROM tmp_tags t
  JOIN public.tags tg ON tg.tag_code = t.tag_code
),
ins_fluors AS (
  INSERT INTO public.fluors (fluor_code, fluor_name)
  SELECT fluor_code, fluor_name FROM tmp_fluors
  ON CONFLICT (fluor_code) DO NOTHING
  RETURNING 1
),
upd_fluors AS (
  UPDATE public.fluors f
  SET    fluor_name = t.fluor_name
  FROM   tmp_fluors t
  WHERE  f.fluor_code = t.fluor_code
     AND f.fluor_name IS DISTINCT FROM t.fluor_name
  RETURNING 1
),
ins_tags AS (
  INSERT INTO public.tags (tag_code, tag_name)
  SELECT tag_code, tag_name FROM tmp_tags
  ON CONFLICT (tag_code) DO NOTHING
  RETURNING 1
),
upd_tags AS (
  UPDATE public.tags t0
  SET    tag_name = t.tag_name
  FROM   tmp_tags t
  WHERE  t0.tag_code = t.tag_code
     AND t0.tag_name IS DISTINCT FROM t.tag_name
  RETURNING 1
),
ins_fusions AS (
  INSERT INTO public.fusions (fusion_code, fusion_name, fluor_id, tag_id)
  SELECT t.fusion_code, t.fusion_name_norm, mf.fluor_id, mt.tag_id
  FROM   tmp_fusions t
  JOIN   map_fluor_ids mf ON mf.fluor_code = t.fluor_code
  LEFT   JOIN map_tag_ids mt ON mt.tag_code = t.tag_code
  ON CONFLICT (fusion_code) DO NOTHING
  RETURNING 1
),
upd_fusions AS (
  UPDATE public.fusions f
  SET    fusion_name = t.fusion_name_norm,
         fluor_id    = mf.fluor_id,
         tag_id      = mt.tag_id
  FROM   tmp_fusions t
  JOIN   map_fluor_ids mf ON mf.fluor_code = t.fluor_code
  LEFT   JOIN map_tag_ids mt ON mt.tag_code = t.tag_code
  WHERE  f.fusion_code = t.fusion_code
     AND (f.fusion_name IS DISTINCT FROM t.fusion_name_norm
          OR f.fluor_id  IS DISTINCT FROM mf.fluor_id
          OR f.tag_id    IS DISTINCT FROM mt.tag_id)
  RETURNING 1
),
pairs AS (
  SELECT DISTINCT
    p.id      AS plasmid_id,
    f.id      AS fusion_id,
    c.plasmid_code,
    t.fusion_code
  FROM clean_with_fluor c
  JOIN tmp_fusions t
    ON t.fusion_name_norm = COALESCE(c.fusion_name, CONCAT_WS(' + ', c.fluor_name, c.tag_name))
  JOIN public.plasmids p
    ON p.code = c.plasmid_code
  JOIN public.fusions  f
    ON f.fusion_code = t.fusion_code
)
INSERT INTO public.join_plasmid_fusions (plasmid_id,        fusion_id,        plasmid_code,   fusion_code)
SELECT                                    plasmid_id,        fusion_id,        plasmid_code,   fusion_code
FROM pairs
ON CONFLICT (plasmid_id, fusion_id) DO NOTHING;
"""

    # 3b) Ensure unique index then run the DML
    with _eng().begin() as cx:
        cx.execute(text("""
          DO $$
          BEGIN
            IF NOT EXISTS (
              SELECT 1 FROM pg_indexes
              WHERE schemaname='public' AND tablename='join_plasmid_fusions'
                AND indexname='uq_join_plasmid_fusions_ids'
            ) THEN
              EXECUTE 'CREATE UNIQUE INDEX uq_join_plasmid_fusions_ids ON public.join_plasmid_fusions(plasmid_id, fusion_id)';
            END IF;
          END$$;
        """))
        cx.execute(text(dml_sql))

    st.success("✅ Upload processed: plasmids upserted, catalogs normalized, fusions linked by IDs.")