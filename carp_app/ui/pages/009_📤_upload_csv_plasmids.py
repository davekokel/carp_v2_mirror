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

import io, os, shlex
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from carp_app.ui.lib.app_ctx import get_engine

PAGE_TITLE = "📤 Upload Plasmids — single format (upsert + link fusions)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)
st.caption("Format: one CSV/XLSX with plasmid fields and fusion fields. Multiple fusions per plasmid are separated by `;` or `|`. Within each fusion use `tag::fluor` (back-compat `tag+fluor`). If `fluor_name` / `tag_name` columns exist, they override parsing of `fusion_name`.")

# ---------------------------------------------------------------------------
# Example template (new format)
# ---------------------------------------------------------------------------
def _example_bytes_name_mime():
    cols = [
        "code","name","nickname","resistance","supports_invitro_rna","notes",
        "plasmid_name","tag_description",
        "fusion_name","fluor_name","tag_name",
    ]
    sample = pd.DataFrame([
        {"code":"pEX001","name":"Example 1","nickname":"ex1","resistance":"Amp","supports_invitro_rna":True,"notes":"columns win","plasmid_name":"Example 1 full name","tag_description":"Mito anchor","fluor_name":"mStayGold","tag_name":"2Xcox8A"},
        {"code":"pEX002","name":"Example 2","nickname":"ex2","resistance":"Kan","supports_invitro_rna":False,"notes":"multi via fusion_name","plasmid_name":"Example 2 full","fusion_name":"2Xcox8A::mStayGold; sec61b::mChilada"},
        {"code":"pEX003","name":"Example 3","nickname":"ex3","resistance":"Amp","supports_invitro_rna":True,"notes":"back-compat +","plasmid_name":"Example 3 full","fusion_name":"sec61b+mChilada"},
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
        if not os.getenv("DB_URL"): st.error("DB_URL not set"); st.stop()
        _ENGINE = get_engine()
    return _ENGINE

def _table_cols(schema: str, table: str) -> list[str]:
    sql = """
      select column_name
      from information_schema.columns
      where table_schema=:s and table_name=:t
      order by ordinal_position
    """
    with _eng().begin() as cx:
        df = pd.read_sql(text(sql), cx, params={"s": schema, "t": table})
    return df["column_name"].tolist()

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
# One-button process: stage → upsert plasmids → load fluors/tags/fusions
# ---------------------------------------------------------------------------
creator_uuid = getattr(user, "id", None)
created_by_uuid = str(creator_uuid) if creator_uuid else None

if st.button("Process upload (upsert plasmids + link fusions)", type="primary", use_container_width=True):
    # shape & stage into raw
    expected = [
        "plasmid_code","plasmid_name","nickname","fluors","tag_description","resistance","notes","supports_invitro_rna",
        "fusion_name","fluor_name","tag_name"
    ]
    # map aliases from sheet to expected
    df_stage = df_raw.copy()
    alias_map = {
        "code":"plasmid_code",
        "name":"plasmid_name",
    }
    for a, b in alias_map.items():
        if a in df_stage.columns and b not in df_stage.columns:
            df_stage[b] = df_stage[a]

    for c in expected:
        if c not in df_stage.columns:
            df_stage[c] = None

    with _eng().begin() as cx:
        # ensure raw schema/table and column rename (tag -> tag_description) once
        cx.execute(text("create schema if not exists raw;"))
        cx.execute(text("""
            create table if not exists raw.plasmids_option1_full (
              plasmid_code text,
              plasmid_name text,
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
        cx.execute(text("""
            do $$
            begin
              if exists (
                select 1 from information_schema.columns
                where table_schema='raw' and table_name='plasmids_option1_full' and column_name='tag'
              ) then
                execute 'alter table raw.plasmids_option1_full rename column tag to tag_description';
              end if;
            end $$;
        """))
        cx.execute(text("truncate raw.plasmids_option1_full;"))

        # bind only expected fields and cast NaN→NULL
        df_stage = df_stage[expected]
        recs_raw = df_stage.where(pd.notna(df_stage), None).to_dict(orient="records")
        cx.execute(text("""
            insert into raw.plasmids_option1_full (
              plasmid_code, plasmid_name, nickname, fluors, tag_description,
              resistance, notes, supports_invitro_rna,
              fusion_name, fluor_name, tag_name
            )
            values (
              :plasmid_code, :plasmid_name, :nickname, :fluors, :tag_description,
              :resistance, :notes, :supports_invitro_rna,
              :fusion_name, :fluor_name, :tag_name
            )
        """), recs_raw)

    # upsert public.plasmids (base fields only)
    plasmid_cols_allowed = ["code","name","nickname","resistance","supports_invitro_rna","notes","created_by"]
    df_pl = pd.DataFrame({
        "code": df_stage["plasmid_code"],
        "name": df_stage["plasmid_name"],
        "nickname": df_stage["nickname"],
        "resistance": df_stage["resistance"],
        "supports_invitro_rna": df_stage["supports_invitro_rna"].map(_norm_bool),
        "notes": df_stage["notes"],
        "created_by": created_by_uuid,
    })
    # drop completely empty codes
    df_pl["code"] = df_pl["code"].fillna("").map(str).str.strip()
    df_pl = df_pl[df_pl["code"] != ""].drop_duplicates(subset=["code"])
    recs_pl = df_pl.where(pd.notna(df_pl), None).to_dict(orient="records")

    with _eng().begin() as cx:
        cols = [c for c in plasmid_cols_allowed if c in df_pl.columns]
        cols_sql = ", ".join(cols)
        vals_sql = ", ".join([f":{c}" for c in cols])
        set_parts = [f"{c}=excluded.{c}" for c in cols if c not in {"code"}]
        cx.execute(text(f"""
            insert into public.plasmids ({cols_sql})
            values ({vals_sql})
            on conflict (code) do update set {', '.join(set_parts)};
        """), recs_pl)

    # loader: derive catalogs and links (require a fluor)
    loader_sql = """
with params as (
  select '[;|]'::text as list_sep, '::|\\+'::text as inner_sep
),
src as (
  select r.*,
         regexp_split_to_array(coalesce(nullif(fusion_name,''),''),(select list_sep from params)) a_fus,
         regexp_split_to_array(coalesce(nullif(fluor_name,''),''),(select list_sep from params)) a_flu,
         regexp_split_to_array(coalesce(nullif(tag_name,''),''),  (select list_sep from params)) a_tag
  from raw.plasmids_option1_full r
),
exploded as (
  select s.plasmid_code, g idx,
         nullif(coalesce(s.a_fus[least(g,nullif(array_length(s.a_fus,1),0))],''),'') fusion_name_raw,
         nullif(coalesce(s.a_flu[least(g,nullif(array_length(s.a_flu,1),0))],''),'') fluor_name_raw,
         nullif(coalesce(s.a_tag[least(g,nullif(array_length(s.a_tag,1),0))],''),'') tag_name_raw
  from src s cross join lateral generate_series(
    1, greatest(coalesce(array_length(s.a_fus,1),1),
                coalesce(array_length(s.a_flu,1),1),
                coalesce(array_length(s.a_tag,1),1))) g
),
parsed as (
  select e.plasmid_code, e.fusion_name_raw, e.fluor_name_raw, e.tag_name_raw,
         case when e.fusion_name_raw is null then null else nullif(trim((regexp_split_to_array(e.fusion_name_raw,(select inner_sep from params)))[2]),'') end as fluor_from_fusion,
         case when e.fusion_name_raw is null then null else nullif(trim((regexp_split_to_array(e.fusion_name_raw,(select inner_sep from params)))[1]),'') end as tag_from_fusion
  from exploded e
),
clean as (
  select plasmid_code,
         nullif(trim(fusion_name_raw),'') as fusion_name,
         case when lower(trim(coalesce(fluor_name_raw, fluor_from_fusion)))='mchialda' then 'mChilada'
              else nullif(trim(coalesce(fluor_name_raw, fluor_from_fusion)),'') end as fluor_name,
         nullif(trim(coalesce(tag_name_raw, tag_from_fusion)),'') as tag_name
  from parsed
),
clean_with_fluor as (
  select * from clean where fluor_name is not null
),
-- fluors
tmp_fluors as (
  select 'flu-'||lower(regexp_replace(fluor_name,'[^A-Za-z0-9]+','-','g')) as fluor_code,
         min(fluor_name) as fluor_name
  from clean_with_fluor
  group by 1
),
-- tags
tmp_tags as (
  select 'tag-'||lower(regexp_replace(tag_name,'[^A-Za-z0-9]+','-','g')) as tag_code,
         min(tag_name) as tag_name
  from clean_with_fluor where tag_name is not null
  group by 1
),
-- fusions
tmp_fusions as (
  select distinct
    'fus-'||lower(regexp_replace(
       concat_ws('--',
         coalesce(fusion_name, concat_ws(' + ', fluor_name, tag_name)),
         'flu-'||lower(regexp_replace(fluor_name,'[^A-Za-z0-9]+','-','g')),
         coalesce(case when tag_name is not null then 'tag-'||lower(regexp_replace(tag_name,'[^A-Za-z0-9]+','-','g')) end,'')
       ), '[^A-Za-z0-9]+','-','g')) as fusion_code,
    coalesce(fusion_name, concat_ws(' + ', fluor_name, tag_name)) as fusion_name_norm,
    'flu-'||lower(regexp_replace(fluor_name,'[^A-Za-z0-9]+','-','g')) as fluor_code,
    case when tag_name is not null then 'tag-'||lower(regexp_replace(tag_name,'[^A-Za-z0-9]+','-','g')) end as tag_code
  from clean_with_fluor
),
-- insert catalogs (do nothing on exist), then update to keep names fresh
ins_fluors as (
  insert into public.fluors (fluor_code, fluor_name)
  select fluor_code, fluor_name from tmp_fluors
  on conflict (fluor_code) do nothing
  returning 1
),
upd_fluors as (
  update public.fluors f
  set fluor_name = t.fluor_name
  from tmp_fluors t
  where f.fluor_code = t.fluor_code
    and f.fluor_name is distinct from t.fluor_name
  returning 1
),
ins_tags as (
  insert into public.tags (tag_code, tag_name)
  select tag_code, tag_name from tmp_tags
  on conflict (tag_code) do nothing
  returning 1
),
upd_tags as (
  update public.tags t0
  set tag_name = t.tag_name
  from tmp_tags t
  where t0.tag_code = t.tag_code
    and t0.tag_name is distinct from t.tag_name
  returning 1
),
ins_fusions as (
  insert into public.fusions (fusion_code, fusion_name, fluor_code, tag_code)
  select fusion_code, fusion_name_norm, fluor_code, tag_code from tmp_fusions
  on conflict (fusion_code) do nothing
  returning 1
),
upd_fusions as (
  update public.fusions f
  set fusion_name = t.fusion_name_norm,
      fluor_code  = t.fluor_code,
      tag_code    = t.tag_code
  from tmp_fusions t
  where f.fusion_code = t.fusion_code
    and (f.fusion_name is distinct from t.fusion_name_norm
         or f.fluor_code is distinct from t.fluor_code
         or f.tag_code   is distinct from t.tag_code)
  returning 1
)
insert into public.plasmid_fusions (plasmid_code, fusion_code, position_in_plasmid)
select distinct
  c.plasmid_code, t.fusion_code, null::int
from clean_with_fluor c
join tmp_fusions t
  on t.fusion_name_norm = coalesce(c.fusion_name, concat_ws(' + ', c.fluor_name, c.tag_name))
on conflict (plasmid_code, fusion_code) do nothing;
"""
    try:
        with _eng().begin() as cx:
            cx.execute(text(loader_sql))
        st.success("Upload processed: plasmids upserted and fusions/fluors/tags linked.")
    except Exception as e:
        st.error(f"Loader failed: {e}")
        with st.expander("Debug SQL"):
            st.code(loader_sql, language="sql")