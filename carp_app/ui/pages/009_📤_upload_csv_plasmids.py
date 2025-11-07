# carp_app/ui/pages/009_📤_upload_plasmids_single.py
from __future__ import annotations
import sys, pathlib, io, os, re
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

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

PAGE_TITLE = "📤 Upload Plasmids — single format (strict resolver)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)
st.caption(
    "CSV/XLSX headers: code, nickname, resistance, supports_invitro_rna, notes, fusion_name. "
    "fusion_name uses ';', '|' or '/' between tokens. Each token must match exactly ONE of: an existing fusion, "
    "a fluor (by code/name/alias), or a tag (by code/name). Ambiguous/unknown tokens are rejected. "
    "Fluor-only or tag-only tokens create/reuse a deterministic fusion; stored fusion names use 'Tag::Fluor'."
)

# ── Example ──────────────────────────────────────────────────────────────────
def _example_bytes_name_mime():
    cols = ["code","nickname","resistance","supports_invitro_rna","notes","fusion_name"]
    sample = pd.DataFrame([
        {"code":"pEX001","nickname":"ex1","resistance":"Amp","supports_invitro_rna":True,"notes":"demo","fusion_name":"2Xcox8A::mStayGold"},
        {"code":"pEX002","nickname":"ex2","resistance":"Kan","supports_invitro_rna":False,"notes":"","fusion_name":"sec61b::mChilada; Lifeact"},
        {"code":"pEX003","nickname":"ex3","resistance":"Amp","supports_invitro_rna":True,"notes":"","fusion_name":"mStayGold"},
        {"code":"pEX004","nickname":"ex4","resistance":"Amp","supports_invitro_rna":True,"notes":"slash list","fusion_name":"mKate2/mCitrine/Electra2"},
    ], columns=cols)
    data = sample.to_csv(index=False).encode()
    return data, "plasmids_single_format_example.csv", "text/csv"

_data, _name, _mime = _example_bytes_name_mime()
st.download_button("⬇️ Example CSV", data=_data, file_name=_name, mime=_mime, type="secondary", use_container_width=True)

# ── Engine ───────────────────────────────────────────────────────────────────
_ENGINE: Engine | None = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        if not os.getenv("DB_URL"): st.error("DB_URL not set"); st.stop()
        _ENGINE = get_engine()
    return _ENGINE

# ── Upload ───────────────────────────────────────────────────────────────────
file = st.file_uploader("Upload single-format file (.csv or .xlsx)", type=["csv","xlsx"])
if not file:
    st.info("Choose a CSV/XLSX to begin."); st.stop()

try:
    if file.name.lower().endswith(".xlsx"):
        df_raw = pd.read_excel(io.BytesIO(file.read()), dtype=object)
    else:
        try:
            df_raw = pd.read_csv(file, dtype=object, encoding="utf-8")
        except UnicodeDecodeError:
            file.seek(0)
            df_raw = pd.read_csv(file, dtype=object, encoding="latin1")
except Exception as e:
    st.error(f"Failed to read file: {e}"); st.stop()

df_raw = df_raw.copy()
df_raw.columns = [str(c).strip().lower() for c in df_raw.columns]

st.subheader("Preview")
st.dataframe(df_raw.head(20), use_container_width=True, hide_index=True)
st.caption(f"{len(df_raw)} rows")

creator_uuid = getattr(user, "id", None)
created_by_uuid = str(creator_uuid) if creator_uuid else None

# ── Process ──────────────────────────────────────────────────────────────────
if st.button("Process upload (strict resolve + upsert + link)", type="primary", use_container_width=True):
    # 1) Shape to strict contract
    expected = ["plasmid_code","nickname","resistance","supports_invitro_rna","notes","fusion_name"]
    df_stage = df_raw.rename(columns={"code":"plasmid_code"}).copy()
    for c in expected:
        if c not in df_stage.columns: df_stage[c] = None
    df_stage = df_stage[expected]

    # QA: blanks allowed (plasmid upsert only)
    blank_mask = df_stage["fusion_name"].fillna("").astype(str).str.strip().eq("")
    blank_rows = df_stage.loc[blank_mask, ["plasmid_code","nickname","resistance","notes"]].copy()
    if not blank_rows.empty:
        st.warning(f"{len(blank_rows)} plasmid(s) have empty fusion_name; they will be upserted without links.")
        st.dataframe(blank_rows, use_container_width=True, hide_index=True)

    # 2) Stage raw
    with _eng().begin() as cx:
        cx.execute(text("create schema if not exists raw;"))
        cx.execute(text("""
            create table if not exists raw.plasmids_option1_full (
              plasmid_code text,
              nickname text,
              resistance text,
              supports_invitro_rna text,
              notes text,
              fusion_name text
            )
        """))
        cx.execute(text("truncate raw.plasmids_option1_full;"))
        recs = df_stage.where(pd.notna(df_stage), None).to_dict(orient="records")
        cx.execute(text("""
            insert into raw.plasmids_option1_full
              (plasmid_code, nickname, resistance, supports_invitro_rna, notes, fusion_name)
            values
              (:plasmid_code, :nickname, :resistance, :supports_invitro_rna, :notes, :fusion_name)
        """), recs)

    # 3) Upsert plasmids (nickname-only; seed name once)
    df_pl = pd.DataFrame({
        "code": df_stage["plasmid_code"].fillna("").map(str).str.strip(),
        "nickname": df_stage["nickname"],
        "resistance": df_stage["resistance"],
        "supports_invitro_rna": df_stage["supports_invitro_rna"].map(lambda v: str(v).strip().lower() in {"1","true","t","yes","y"}),
        "notes": df_stage["notes"],
        "created_by": created_by_uuid,
    })
    df_pl = df_pl[df_pl["code"] != ""].drop_duplicates(subset=["code"])
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

    # 4) Strict preflight resolution (fluor-wins; split fallback; reversed support)
    with _eng().begin() as cx:
        fus = cx.execute(text("""
            SELECT id::text AS id, lower(coalesce(fusion_name,fusion_code)) AS k
            FROM public.fusions
        """)).mappings().all()
        fl = cx.execute(text("""
            SELECT id::text AS id, lower(coalesce(fluor_name,fluor_code)) AS k FROM public.fluors
            UNION ALL
            SELECT f.id::text, lower(a) AS k
            FROM public.fluors f
            CROSS JOIN LATERAL unnest(coalesce(f.alt_names,'{}'::text[])) a(a)
        """)).mappings().all()
        tg = cx.execute(text("""
            SELECT id::text AS id, lower(coalesce(tag_name,tag_code)) AS k FROM public.tags
        """)).mappings().all()

    fus_idx, flu_idx, tag_idx = {}, {}, {}
    for r in fus:
        if r["k"]: fus_idx.setdefault(r["k"], set()).add(r["id"])
    for r in fl:
        if r["k"]: flu_idx.setdefault(r["k"], set()).add(r["id"])
    for r in tg:
        if r["k"]: tag_idx.setdefault(r["k"], set()).add(r["id"])
    
    fluor_idx = flu_idx  # alias for legacy references

    def split_tokens(s: str) -> list[str]:
        if not s:
            return []
        # also split '/' and drop trivial "nan"/"none" entries
        toks = [t.strip() for t in re.split(r"[;|/]", str(s))]
        return [t for t in toks if t and t.strip().lower() not in {"nan","none"}]

    problems = []
    res_fusion, res_fluor, res_tag, res_pair = [], [], [], []

    for r in df_stage.itertuples(index=False):
        code = str(getattr(r, "plasmid_code") or "").strip()
        toks = split_tokens(str(getattr(r, "fusion_name") or ""))
        if not code or not toks:
            continue
        for tok in toks:
            key = tok.lower()

            # Compound tokens: try Tag::Fluor then Fluor::Tag
            if "::" in key or "+" in key:
                fus_ids = list(fus_idx.get(key, []))
                if len(fus_ids) == 1:
                    res_fusion.append({"c": code, "id": fus_ids[0]})
                    continue
                elif len(fus_ids) > 1:
                    problems.append({"plasmid_code": code, "token": tok, "categories": "fusion:multiple"})
                    continue

                parts = re.split(r"::|\+", key)
                if len(parts) == 2:
                    left, right = parts[0].strip().lower(), parts[1].strip().lower()

                    # Tag::Fluor
                    tag_ids   = list(tag_idx.get(left,  []))
                    fluor_ids = list(fluor_idx.get(right, []))
                    if len(tag_ids) == 1 and len(fluor_ids) == 1:
                        res_pair.append({"c": code, "tag_id": tag_ids[0], "fluor_id": fluor_ids[0]})
                        continue

                    # Fluor::Tag (reversed)
                    tag_ids_r   = list(tag_idx.get(right, []))
                    fluor_ids_r = list(fluor_idx.get(left,  []))
                    if len(tag_ids_r) == 1 and len(fluor_ids_r) == 1:
                        res_pair.append({"c": code, "tag_id": tag_ids_r[0], "fluor_id": fluor_ids_r[0]})
                        continue

                    problems.append({
                        "plasmid_code": code,
                        "token": tok,
                        "categories": f"split-missing: tagL={len(tag_ids)}, fluorR={len(fluor_ids)}; tagR={len(tag_ids_r)}, fluorL={len(fluor_ids_r)}"
                    })
                    continue

                problems.append({"plasmid_code": code, "token": tok, "categories": "bad-split"})
                continue

            # Single token — fluor-wins over fusion; tag-wins over fusion; only ambiguous if tag + fluor both hit
            fus_ids   = list(fus_idx.get(key, []))
            fluor_ids = list(fluor_idx.get(key, []))
            tag_ids   = list(tag_idx.get(key, []))

            # Fluor-only (even if a fluor-only fusion exists with same name)
            if len(fluor_ids) == 1 and len(tag_ids) == 0:
                res_fluor.append({"c": code, "id": fluor_ids[0]})
                continue

            # Tag-only (even if a fusion exists with same name)
            if len(tag_ids) == 1 and len(fluor_ids) == 0:
                res_tag.append({"c": code, "id": tag_ids[0]})
                continue

            # Exact fusion only
            if len(fus_ids) == 1 and len(fluor_ids) == 0 and len(tag_ids) == 0:
                res_fusion.append({"c": code, "id": fus_ids[0]})
                continue

            # Otherwise truly ambiguous/unknown
            cats = []
            if fus_ids:   cats.append("fusion")
            if fluor_ids: cats.append("fluor")
            if tag_ids:   cats.append("tag")
            problems.append({"plasmid_code": code, "token": tok, "categories": ",".join(cats) if cats else "none"})

    if problems:
        bad = pd.DataFrame(problems)
        st.error(f"{len(bad)} fusion token(s) are unknown or ambiguous. Fix CSV and re-upload.")
        st.dataframe(bad, use_container_width=True, hide_index=True)
        st.download_button("⬇︎ Problem tokens (CSV)", data=bad.to_csv(index=False).encode("utf-8"),
                           file_name="plasmids_problem_tokens.csv", mime="text/csv",
                           use_container_width=True)
        st.stop()

    # 5) Stage resolutions (dedup per channel)
    keys_fus  = {(r["c"], r["id"]) for r in res_fusion}
    keys_flu  = {(r["c"], r["id"]) for r in res_fluor}
    keys_tag  = {(r["c"], r["id"]) for r in res_tag}
    keys_pair = {(r["c"], r["tag_id"], r["fluor_id"]) for r in res_pair}
    res_fusion = [{"c":c,"id":i} for (c,i) in keys_fus]
    res_fluor  = [{"c":c,"id":i} for (c,i) in keys_flu]
    res_tag    = [{"c":c,"id":i} for (c,i) in keys_tag]
    res_pair   = [{"c":c,"tag_id":t,"fluor_id":f} for (c,t,f) in keys_pair]

    with _eng().begin() as cx:
        cx.execute(text("CREATE TEMP TABLE _res_fusion(plasmid_code text, fusion_id uuid, PRIMARY KEY(plasmid_code, fusion_id)) ON COMMIT DROP;"))
        cx.execute(text("CREATE TEMP TABLE _res_fluor (plasmid_code text, fluor_id  uuid, PRIMARY KEY(plasmid_code, fluor_id))  ON COMMIT DROP;"))
        cx.execute(text("CREATE TEMP TABLE _res_tag   (plasmid_code text, tag_id    uuid, PRIMARY KEY(plasmid_code, tag_id))    ON COMMIT DROP;"))
        cx.execute(text("CREATE TEMP TABLE _res_pair  (plasmid_code text, tag_id uuid, fluor_id uuid, PRIMARY KEY(plasmid_code, tag_id, fluor_id)) ON COMMIT DROP;"))

        if res_fusion:
            cx.execute(text("INSERT INTO _res_fusion VALUES (:c, :id)"), res_fusion)
        if res_fluor:
            cx.execute(text("INSERT INTO _res_fluor  VALUES (:c, :id)"), res_fluor)
        if res_tag:
            cx.execute(text("INSERT INTO _res_tag    VALUES (:c, :id)"), res_tag)
        if res_pair:
            cx.execute(text("INSERT INTO _res_pair   VALUES (:c, :tag_id, :fluor_id)"), res_pair)

        # 6) Create/reuse fusions, then link
        dml = text("""
WITH pl AS (
  SELECT code, id FROM public.plasmids
),
pairs_fusion AS (
  SELECT p.id AS plasmid_id, rf.fusion_id
  FROM _res_fusion rf
  JOIN pl p ON p.code = rf.plasmid_code
),
-- fluor-only
fluor_pairs AS (
  SELECT DISTINCT p.id AS plasmid_id,
         COALESCE(fu.id, (SELECT id FROM public.fusions WHERE fluor_id=rf.fluor_id AND tag_id IS NULL LIMIT 1)) AS fusion_id,
         rf.fluor_id
  FROM _res_fluor rf
  JOIN pl p ON p.code = rf.plasmid_code
  LEFT JOIN public.fusions fu ON fu.fluor_id=rf.fluor_id AND fu.tag_id IS NULL
),
ins_fluor_fusions AS (
  INSERT INTO public.fusions (fusion_code, fusion_name, fluor_id, tag_id)
  SELECT
    'fus-'||encode(digest('fluor:'||rf.fluor_id::text,'sha256'),'hex'),
    (SELECT fluor_name FROM public.fluors WHERE id=rf.fluor_id),
    rf.fluor_id,
    NULL
  FROM fluor_pairs fp
  JOIN _res_fluor rf ON rf.fluor_id = fp.fluor_id
  WHERE fp.fusion_id IS NULL
  ON CONFLICT (fusion_code) DO NOTHING
  RETURNING id
),
fluor_pairs2 AS (
  SELECT DISTINCT p.id AS plasmid_id, fu.id AS fusion_id
  FROM _res_fluor rf
  JOIN pl p ON p.code=rf.plasmid_code
  JOIN public.fusions fu ON fu.fluor_id=rf.fluor_id AND fu.tag_id IS NULL
),
-- tag-only
tag_pairs AS (
  SELECT DISTINCT p.id AS plasmid_id,
         COALESCE(fu.id, (SELECT id FROM public.fusions WHERE tag_id=rt.tag_id AND fluor_id IS NULL LIMIT 1)) AS fusion_id,
         rt.tag_id
  FROM _res_tag rt
  JOIN pl p ON p.code = rt.plasmid_code
  LEFT JOIN public.fusions fu ON fu.tag_id=rt.tag_id AND fu.fluor_id IS NULL
),
ins_tag_fusions AS (
  INSERT INTO public.fusions (fusion_code, fusion_name, fluor_id, tag_id)
  SELECT
    'fus-'||encode(digest('tag:'||rt.tag_id::text,'sha256'),'hex'),
    (SELECT tag_name FROM public.tags WHERE id=rt.tag_id),
    NULL,
    rt.tag_id
  FROM tag_pairs tp
  JOIN _res_tag rt ON rt.tag_id = tp.tag_id
  WHERE tp.fusion_id IS NULL
  ON CONFLICT (fusion_code) DO NOTHING
  RETURNING id
),
tag_pairs2 AS (
  SELECT DISTINCT p.id AS plasmid_id, fu.id AS fusion_id
  FROM _res_tag rt
  JOIN pl p ON p.code=rt.plasmid_code
  JOIN public.fusions fu ON fu.tag_id=rt.tag_id AND fu.fluor_id IS NULL
),
-- tag+fluor pair
pair_pairs AS (
  SELECT DISTINCT p.id AS plasmid_id,
         COALESCE(fu.id, (SELECT id FROM public.fusions WHERE tag_id=rp.tag_id AND fluor_id=rp.fluor_id LIMIT 1)) AS fusion_id,
         rp.tag_id, rp.fluor_id
  FROM _res_pair rp
  JOIN pl p ON p.code = rp.plasmid_code
  LEFT JOIN public.fusions fu ON fu.tag_id=rp.tag_id AND fu.fluor_id=rp.fluor_id
),
ins_pair_fusions AS (
  INSERT INTO public.fusions (fusion_code, fusion_name, fluor_id, tag_id)
  SELECT
    'fus-'||encode(digest('pair:'||rp.tag_id::text||':'||rp.fluor_id::text,'sha256'),'hex'),
    (SELECT tag_name   FROM public.tags   WHERE id=rp.tag_id) || '::' ||
    (SELECT fluor_name FROM public.fluors WHERE id=rp.fluor_id),
    rp.fluor_id,
    rp.tag_id
  FROM pair_pairs pp
  JOIN _res_pair rp ON rp.tag_id=pp.tag_id AND rp.fluor_id=pp.fluor_id
  WHERE pp.fusion_id IS NULL
  ON CONFLICT (fusion_code) DO NOTHING
  RETURNING id
),
pair_pairs2 AS (
  SELECT DISTINCT p.id AS plasmid_id, fu.id AS fusion_id
  FROM _res_pair rp
  JOIN pl p ON p.code=rp.plasmid_code
  JOIN public.fusions fu ON fu.tag_id=rp.tag_id AND fu.fluor_id=rp.fluor_id
),
all_pairs AS (
  SELECT * FROM pairs_fusion
  UNION ALL SELECT * FROM fluor_pairs2
  UNION ALL SELECT * FROM tag_pairs2
  UNION ALL SELECT * FROM pair_pairs2
)
INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id)
SELECT DISTINCT plasmid_id, fusion_id
FROM all_pairs
WHERE fusion_id IS NOT NULL
ON CONFLICT (plasmid_id, fusion_id) DO NOTHING;
        """)
        cx.execute(dml)

# Post-import: ensure FT masters exist and backfill ft_proteins from plasmid↔fusion links
with _eng().begin() as cx:
    cx.execute(text("""
        -- 1) Ensure an FT master for each plasmid code that now has a linked fusion
        INSERT INTO public.treatments_fluorescent (ft_code, ft_text, created_by)
        SELECT s.ft_code, ''::text, 'plasmids-import'
        FROM (
          SELECT DISTINCT p.code AS ft_code
          FROM public.plasmids p
          JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
        ) AS s
        LEFT JOIN public.treatments_fluorescent t
          ON t.ft_code = s.ft_code
        WHERE t.ft_code IS NULL;

        -- 2) Populate/refresh per-FT protein components
        INSERT INTO public.ft_proteins (ft_code, fluor_code, tag_code)
        SELECT DISTINCT
          p.code AS ft_code,
          fl.fluor_code,
          tg.tag_code
        FROM public.plasmids p
        JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
        JOIN public.fusions fu               ON fu.id = jpf.fusion_id
        LEFT JOIN public.fluors  fl          ON fl.id = fu.fluor_id
        LEFT JOIN public.tags    tg          ON tg.id = fu.tag_id
        WHERE fl.fluor_code IS NOT NULL
        ON CONFLICT (ft_code, COALESCE(tag_code,'∅'), fluor_code) DO NOTHING;
    """))

    st.success("✅ Upload processed: plasmids upserted; tokens strictly resolved; fusions linked by IDs.")