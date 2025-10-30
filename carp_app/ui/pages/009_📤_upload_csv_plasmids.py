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
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.ui.lib.app_ctx import get_engine

PAGE_TITLE = "📤 Upload Plasmids (Upsert on code + optional fusions loader)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)

st.caption("New format supports multi-fusions. Use `;` or `|` to separate multiple fusions per plasmid. Inside each fusion use `tag::fluor` (back-compat: `tag+fluor`). If `fluor_name` / `tag_name` columns are present, they override parsing of `fusion_name`.")

def _example_plasmids_bytes_name_mime():
    cols = [
        "code","name","nickname","resistance","supports_invitro_rna","notes",
        "fusion_name","fluor_name","tag_name"
    ]
    sample = pd.DataFrame([
        {"code":"pEX001","name":"Example 1","nickname":"ex1","resistance":"Amp","supports_invitro_rna":True,"notes":"single fusion via columns","fluor_name":"mStayGold","tag_name":"2Xcox8A"},
        {"code":"pEX002","name":"Example 2","nickname":"ex2","resistance":"Kan","supports_invitro_rna":False,"notes":"multi fusions in fusion_name","fusion_name":"2Xcox8A::mStayGold; sec61b::mChilada"},
        {"code":"pEX003","name":"Example 3","nickname":"ex3","resistance":"Amp","supports_invitro_rna":True,"notes":"back-compat using +","fusion_name":"Halo+sec61b"},
    ], columns=cols)
    data = sample.to_csv(index=False).encode()
    return data, "plasmids_new_format_example.csv", "text/csv"

_data, _name, _mime = _example_plasmids_bytes_name_mime()
st.download_button("⬇️ Download example — New plasmids format", data=_data, file_name=_name, mime=_mime, type="secondary", width="stretch")

_ENGINE: Engine | None = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

def _list_table_columns(schema: str, table: str) -> list[str]:
    sql = """
      select column_name
      from information_schema.columns
      where table_schema=:schema and table_name=:table
      order by ordinal_position
    """
    with _eng().begin() as cx:
        df = pd.read_sql(text(sql), cx, params={"schema": schema, "table": table})
    return df["column_name"].tolist()

def _clean_df_for_table(df: pd.DataFrame, table_cols: list[str]) -> pd.DataFrame:
    keep = [c for c in df.columns if c in table_cols]
    out = df[keep].copy()
    for c in out.columns:
        if pd.api.types.is_string_dtype(out[c]) or out[c].dtype == object:
            out[c] = out[c].where(out[c].notna(), None)
            out[c] = out[c].map(lambda x: x.strip() if isinstance(x, str) else x)
    return out.dropna(how="all", subset=keep)

file = st.file_uploader("Upload plasmids file (.csv or .xlsx)", type=["csv", "xlsx"])
chunk_size = st.number_input("Batch size", 100, 5000, 1000, 100)

creator_uuid = getattr(user, "id", None)
created_by_uuid = str(creator_uuid) if creator_uuid else None

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
st.subheader("Preview of uploaded data")
st.dataframe(df_raw.head(20), width="stretch", hide_index=True)
st.caption(f"{len(df_raw)} rows total")

schema, table = "public", "plasmids"
table_cols = _list_table_columns(schema, table)
df = _clean_df_for_table(df_raw, table_cols)

if "created_by" in table_cols and "created_by" not in df.columns:
    df["created_by"] = created_by_uuid

if "supports_invitro_rna" in df.columns:
    def _norm_flag(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return False
        s = str(v).strip().lower()
        return s in {"1","true","t","yes","y"}
    df["supports_invitro_rna"] = df["supports_invitro_rna"].map(_norm_flag)

st.success(f"Columns to upsert into public.plasmids: {', '.join(df.columns)}")
st.caption(f"DB_URL → {os.getenv('DB_URL')}")
st.caption(f"CSV rows (for plasmids upsert): {len(df)}")

c1, c2 = st.columns(2)

with c1:
    if st.button("Upsert plasmids (on code)", type="primary", use_container_width=True):
        ok = fail = rna_ok = rna_fail = 0
        cols = list(df.columns)
        cols_sql = ", ".join(cols)
        vals_sql = ", ".join([f":{c}" for c in cols])
        updateable = ["name","nickname","resistance","notes","created_by","supports_invitro_rna"]
        set_parts = [f"{c} = EXCLUDED.{c}" for c in cols if c in updateable and c in table_cols]
        if not set_parts:
            st.error("No updateable columns detected; add at least one of: " + ", ".join(updateable))
            st.stop()
        sql_upsert = f"""
        INSERT INTO public.plasmids ({cols_sql})
        VALUES ({vals_sql})
        ON CONFLICT (code)
        DO UPDATE SET {', '.join(set_parts)};
        """
        sql_ensure = text("select * from public.ensure_rna_for_plasmid(:plasmid_code, 'RNA', :rna_name, :by, :notes)")
        recs: List[Dict[str, Any]] = df.where(pd.notna(df), None).to_dict(orient="records")
        with _eng().begin() as cx:
            try:
                cx.execute(text(sql_upsert), recs)
                ok += len(recs)
            except Exception as e:
                fail += len(recs)
                st.error(f"❌ Upsert failed for {len(recs)} rows: {e}")
            for r in recs:
                try:
                    if r.get("supports_invitro_rna") is True:
                        code = (r.get("code") or "").strip()
                        if not code:
                            rna_fail += 1
                            continue
                        cx.execute(sql_ensure, {
                            "plasmid_code": code,
                            "rna_name": (r.get("name") or f"{code}-RNA"),
                            "by": created_by_uuid,
                            "notes": r.get("notes"),
                        })
                        rna_ok += 1
                except Exception as e:
                    rna_fail += 1
                    st.error(f"RNA ensure failed for {r.get('code')}: {e}")
        st.success(f"Done. Upserted: {ok}. Failed: {fail}. RNA ensured: {rna_ok}. RNA failures: {rna_fail}.")

with c2:
    st.write(" ")
    st.write("**Or** load fusions/fluors/tags from this file → `fluors`,`tags`,`fusions`,`plasmid_fusions`")
    wants_loader = st.checkbox("Enable fusions loader (uses raw.plasmids_option1_full)")
    if wants_loader and st.button("Load fusions/fluors/tags", type="secondary", use_container_width=True):
        for need in ["plasmid_code","fusion_name","fluor_name","tag_name"]:
            if need not in df_raw.columns:
                st.error(f"Missing required column for loader: {need}")
                st.stop()
        with _eng().begin() as cx:
            cx.execute(text("create schema if not exists raw;"))
            cx.execute(text("""
                create table if not exists raw.plasmids_option1_full (
                  plasmid_code text,
                  plasmid_name text,
                  nickname text,
                  fluors text,
                  tag text,
                  resistance text,
                  notes text,
                  supports_invitro_rna text,
                  fusion_name text,
                  fluor_name text,
                  tag_name text
                )
            """))
            cx.execute(text("truncate raw.plasmids_option1_full;"))
            recs_raw = df_raw.where(pd.notna(df_raw), None).to_dict(orient="records")
            cx.execute(text("""
                insert into raw.plasmids_option1_full (
                  plasmid_code, plasmid_name, nickname, fluors, tag, resistance, notes,
                  supports_invitro_rna, fusion_name, fluor_name, tag_name
                )
                values (
                  :plasmid_code, :plasmid_name, :nickname, :fluors, :tag, :resistance, :notes,
                  :supports_invitro_rna, :fusion_name, :fluor_name, :tag_name
                )
            """), recs_raw)
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
         case when e.fusion_name_raw is null then null
              else nullif(trim((regexp_split_to_array(e.fusion_name_raw,(select inner_sep from params)))[2]),'') end as fluor_from_fusion,
         case when e.fusion_name_raw is null then null
              else nullif(trim((regexp_split_to_array(e.fusion_name_raw,(select inner_sep from params)))[1]),'') end as tag_from_fusion
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
fluor_catalog as (select distinct fluor_name from clean where fluor_name is not null),
tag_catalog   as (select distinct tag_name   from clean where tag_name   is not null),
up_fluors as (
  insert into public.fluors (fluor_code, fluor_name)
  select 'flu-'||lower(regexp_replace(fluor_name,'[^A-Za-z0-9]+','-','g')), fluor_name
  from fluor_catalog
  on conflict (fluor_code) do update set fluor_name=excluded.fluor_name
  returning 1
),
up_tags as (
  insert into public.tags (tag_code, tag_name)
  select 'tag-'||lower(regexp_replace(tag_name,'[^A-Za-z0-9]+','-','g')), tag_name
  from tag_catalog
  on conflict (tag_code) do update set tag_name=excluded.tag_name
  returning 1
),
fusion_rows_base as (
  select distinct
    coalesce(fusion_name, concat_ws(' + ', fluor_name, tag_name)) fusion_name_norm,
    case when fluor_name is not null then 'flu-'||lower(regexp_replace(fluor_name,'[^A-Za-z0-9]+','-','g')) end fluor_code,
    case when tag_name   is not null then 'tag-'||lower(regexp_replace(tag_name,  '[^A-Za-z0-9]+','-','g')) end tag_code
  from clean
  where fusion_name is not null or fluor_name is not null or tag_name is not null
),
fusion_codes as (
  select distinct
    'fus-'||lower(regexp_replace(concat_ws('--',fusion_name_norm,coalesce(fluor_code,''),coalesce(tag_code,'')),'[^A-Za-z0-9]+','-','g')) fusion_code,
    min(fusion_name_norm) fusion_name_norm,
    min(fluor_code) fluor_code,
    min(tag_code) tag_code
  from fusion_rows_base
  group by 1
),
up_fusions as (
  insert into public.fusions (fusion_code, fusion_name, fluor_code, tag_code)
  select fusion_code, fusion_name_norm, fluor_code, tag_code
  from fusion_codes
  on conflict (fusion_code) do update
    set fusion_name=excluded.fusion_name, fluor_code=excluded.fluor_code, tag_code=excluded.tag_code
  returning 1
)
insert into public.plasmid_fusions (plasmid_code, fusion_code, position_in_plasmid)
select distinct
  c.plasmid_code,
  'fus-'||lower(regexp_replace(
    concat_ws('--',
      coalesce(c.fusion_name, concat_ws(' + ', c.fluor_name, c.tag_name)),
      coalesce(case when c.fluor_name is not null then 'flu-'||lower(regexp_replace(c.fluor_name,'[^A-Za-z0-9]+','-','g')) end,''),
      coalesce(case when c.tag_name   is not null then 'tag-'||lower(regexp_replace(c.tag_name,  '[^A-Za-z0-9]+','-','g')) end,'')
    ),'[^A-Za-z0-9]+','-','g')),
  null::int
from clean c
where c.plasmid_code is not null
  and (c.fusion_name is not null or c.fluor_name is not null or c.tag_name is not null)
on conflict (plasmid_code,fusion_code) do nothing;
"""
            cx.execute(text(loader_sql))
        st.success("Loaded fusions/fluors/tags into public.fluors/tags/fusions and public.plasmid_fusions from this file.")