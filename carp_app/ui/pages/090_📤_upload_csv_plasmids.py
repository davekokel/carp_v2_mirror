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

PAGE_TITLE = "📤 Upload Plasmids — single format (strict)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)
st.caption(
    "CSV/XLSX headers (exact): plasmid_code, nickname, resistance, supports_invitro_rna, notes, fusion_name.\n"
    "• Elements are '|' delimited. • Pairs use '::' and can be tag::fluor or fluor::tag.\n"
    "No '/' allowed. Unknown or ambiguous tokens are rejected."
)

# Example
def _example_bytes_name_mime():
    cols = ["plasmid_code","nickname","resistance","supports_invitro_rna","notes","fusion_name"]
    sample = pd.DataFrame([
        {"plasmid_code":"pEX001","nickname":"ex1","resistance":"Amp","supports_invitro_rna":True,"notes":"demo","fusion_name":"2xLynk::mStayGold"},
        {"plasmid_code":"pEX002","nickname":"ex2","resistance":"Kan","supports_invitro_rna":False,"notes":"","fusion_name":"mScarlet|mTFP1"},
        {"plasmid_code":"pEX003","nickname":"ex3","resistance":"Amp","supports_invitro_rna":True,"notes":"","fusion_name":"mStayGold"},
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
    expected = ["plasmid_code","nickname","resistance","supports_invitro_rna","notes","fusion_name"]
    df = df_raw.rename(columns={"code":"plasmid_code"}).copy()
    for c in expected:
        if c not in df.columns: df[c] = None
    df = df[expected]
    df["plasmid_code"] = df["plasmid_code"].astype(str).str.strip()
    df["supports_invitro_rna"] = df["supports_invitro_rna"].map(lambda v: str(v).strip().lower() in {"1","true","t","yes","y"})

    # Disallow '/' in fusion_name (strict spec)
    bad_slash = df[df["fusion_name"].fillna("").astype(str).str.contains("/", regex=False)]
    if not bad_slash.empty:
        st.error("Invalid '/' found in fusion_name. Use '|' for lists and '::' for pairs. Fix and re-upload.")
        st.dataframe(bad_slash[["plasmid_code","fusion_name"]], use_container_width=True, hide_index=True)
        st.stop()

    # Upsert plasmids
    df_pl = pd.DataFrame({
        "code": df["plasmid_code"],
        "nickname": df["nickname"],
        "name": df["nickname"].where(df["nickname"].notna() & (df["nickname"]!=""), df["plasmid_code"]),
        "resistance": df["resistance"],
        "supports_invitro_rna": df["supports_invitro_rna"],
        "notes": df["notes"],
        "created_by": created_by_uuid,
    }).drop_duplicates(subset=["code"])
    with _eng().begin() as cx:
        cx.execute(text("""
            INSERT INTO public.plasmids (code, name, nickname, resistance, supports_invitro_rna, notes, created_by)
            VALUES (:code, :name, :nickname, :resistance, :supports_invitro_rna, :notes, :created_by)
            ON CONFLICT (code) DO UPDATE
              SET name                 = EXCLUDED.name,
                  nickname             = EXCLUDED.nickname,
                  resistance           = EXCLUDED.resistance,
                  supports_invitro_rna = EXCLUDED.supports_invitro_rna,
                  notes                = COALESCE(EXCLUDED.notes, public.plasmids.notes),
                  created_by           = COALESCE(EXCLUDED.created_by, public.plasmids.created_by)
        """), df_pl.where(pd.notna(df_pl), None).to_dict(orient="records"))

    # Build resolver indexes (lowercased keys)
    with _eng().begin() as cx:
        # fusions by name/code
        fusions = cx.execute(text("SELECT id::text AS id, lower(coalesce(fusion_name,fusion_code)) AS k FROM public.fusions")).mappings().all()
        # fluors by name/code and alt_names[]
        fluors = cx.execute(text("""
            SELECT id::text AS id, lower(coalesce(fluor_name,fluor_code)) AS k FROM public.fluors
            UNION ALL
            SELECT f.id::text, lower(a) AS k FROM public.fluors f
            CROSS JOIN LATERAL unnest(coalesce(f.alt_names,'{}'::text[])) a(a)
        """)).mappings().all()
        # tags by name/code
        tags = cx.execute(text("SELECT id::text AS id, lower(coalesce(tag_name,tag_code)) AS k FROM public.tags")).mappings().all()

    f_idx, fl_idx, tg_idx = {}, {}, {}
    for r in fusions:
        if r["k"]: f_idx.setdefault(r["k"], set()).add(r["id"])
    for r in fluors:
        if r["k"]: fl_idx.setdefault(r["k"], set()).add(r["id"])
    for r in tags:
        if r["k"]: tg_idx.setdefault(r["k"], set()).add(r["id"])

    def _split_list(s: str) -> list[str]:
        if not s or str(s).strip().lower() in {"nan","none"}:
            return []
        return [t.strip() for t in str(s).split("|") if t.strip()]

    problems = []
    res_fusion, res_fluor, res_tag, res_pair = [], [], [], []

    for r in df.itertuples(index=False):
        code = (r.plasmid_code or "").strip()
        toks = _split_list(getattr(r, "fusion_name", ""))
        if not code or not toks:
            continue

        for tok in toks:
            key = tok.lower()

            # pair?
            if "::" in key:
                parts = [p.strip().lower() for p in key.split("::")]
                if len(parts) != 2:
                    problems.append({"plasmid_code": code, "token": tok, "reason": "bad-pair"})
                    continue

                # existing fusion by exact display/code
                fids = list(f_idx.get(key, []))
                if len(fids) == 1:
                    res_fusion.append({"c": code, "id": fids[0]})
                    continue
                elif len(fids) > 1:
                    problems.append({"plasmid_code": code, "token": tok, "reason": "ambiguous-existing-fusion"})
                    continue

                a, b = parts
                # try a=tag, b=fluor
                tagL = list(tg_idx.get(a, []))
                fluR = list(fl_idx.get(b, []))
                if len(tagL) == 1 and len(fluR) == 1:
                    res_pair.append({"c": code, "tag_id": tagL[0], "fluor_id": fluR[0]})
                    continue
                # try a=fluor, b=tag
                fluL = list(fl_idx.get(a, []))
                tagR = list(tg_idx.get(b, []))
                if len(fluL) == 1 and len(tagR) == 1:
                    res_pair.append({"c": code, "tag_id": tagR[0], "fluor_id": fluL[0]})
                    continue

                problems.append({"plasmid_code": code, "token": tok, "reason": "unresolved-pair"})
                continue

            # single token: precedence → fluor wins, then tag, then fusion (only if no fluor/tag)
            fids = list(f_idx.get(key, []))
            fls  = list(fl_idx.get(key, []))
            tgs  = list(tg_idx.get(key, []))

            # Fluor-only wins (even if a fusion with same label exists)
            if len(fls) == 1 and len(tgs) == 0:
                res_fluor.append({"c": code, "id": fls[0]})
                continue

            # Tag-only wins (even if a fusion with same label exists)
            if len(tgs) == 1 and len(fls) == 0:
                res_tag.append({"c": code, "id": tgs[0]})
                continue

            # Exact fusion only if no fluor AND no tag matched
            if len(fids) == 1 and len(fls) == 0 and len(tgs) == 0:
                res_fusion.append({"c": code, "id": fids[0]})
                continue

            # Otherwise truly ambiguous/unknown
            cats = []
            if fids: cats.append("fusion")
            if fls:  cats.append("fluor")
            if tgs:  cats.append("tag")
            problems.append({
                "plasmid_code": code,
                "token": tok,
                "reason": "ambiguous" if cats else "unknown",
                "candidates": ",".join(cats)
            })

    if problems:
        bad = pd.DataFrame(problems)
        st.error(f"{len(bad)} fusion token(s) are unknown or ambiguous. Fix CSV and re-upload.")
        st.dataframe(bad, use_container_width=True, hide_index=True)
        st.download_button("⬇︎ Problem tokens (CSV)", data=bad.to_csv(index=False).encode("utf-8"),
                           file_name="plasmids_problem_tokens.csv", mime="text/csv",
                           use_container_width=True)
        st.stop()

    # Stage unique resolutions
    keys_fus  = {(r["c"], r["id"]) for r in res_fusion}
    keys_flu  = {(r["c"], r["id"]) for r in res_fluor}
    keys_tag  = {(r["c"], r["id"]) for r in res_tag}
    keys_pair = {(r["c"], r["tag_id"], r["fluor_id"]) for r in res_pair}
    res_fusion = [{"c":c,"id":i} for (c,i) in keys_fus]
    res_fluor  = [{"c":c,"id":i} for (c,i) in keys_flu]
    res_tag    = [{"c":c,"id":i} for (c,i) in keys_tag]
    res_pair   = [{"c":c,"tag_id":t,"fluor_id":f} for (c,t,f) in keys_pair]

    with _eng().begin() as cx:
        cx.execute(text("CREATE TEMP TABLE _res_fusion(plasmid_code text, fusion_id uuid, PRIMARY KEY(plasmid_code, fusion_id)) ON COMMIT DROP"))
        cx.execute(text("CREATE TEMP TABLE _res_fluor (plasmid_code text, fluor_id  uuid, PRIMARY KEY(plasmid_code, fluor_id))  ON COMMIT DROP"))
        cx.execute(text("CREATE TEMP TABLE _res_tag   (plasmid_code text, tag_id    uuid, PRIMARY KEY(plasmid_code, tag_id))    ON COMMIT DROP"))
        cx.execute(text("CREATE TEMP TABLE _res_pair  (plasmid_code text, tag_id uuid, fluor_id uuid, PRIMARY KEY(plasmid_code, tag_id, fluor_id)) ON COMMIT DROP"))

        if res_fusion: cx.execute(text("INSERT INTO _res_fusion VALUES (:c, :id)"), res_fusion)
        if res_fluor:  cx.execute(text("INSERT INTO _res_fluor  VALUES (:c, :id)"), res_fluor)
        if res_tag:    cx.execute(text("INSERT INTO _res_tag    VALUES (:c, :id)"), res_tag)
        if res_pair:   cx.execute(text("INSERT INTO _res_pair   VALUES (:c, :tag_id, :fluor_id)"), res_pair)

        # Create or reuse fusions, then link plasmids → fusions
        cx.execute(text("""
WITH pl AS (SELECT code, id FROM public.plasmids),

pairs_fusion AS (
  SELECT p.id AS plasmid_id, rf.fusion_id
  FROM _res_fusion rf JOIN pl p ON p.code = rf.plasmid_code
),

-- fluor-only → ensure a fluor-only fusion exists
fluor_pairs AS (
  SELECT DISTINCT p.id AS plasmid_id, rf.fluor_id,
         (SELECT id FROM public.fusions WHERE fluor_id=rf.fluor_id AND tag_id IS NULL LIMIT 1) AS fusion_id
  FROM _res_fluor rf JOIN pl p ON p.code = rf.plasmid_code
),
ins_fluor AS (
  INSERT INTO public.fusions (fusion_code, fusion_name, fluor_id, tag_id)
  SELECT DISTINCT
    'fus-'||encode(digest('fluor:'||rf.fluor_id::text,'sha256'),'hex'),
    fl.fluor_name, rf.fluor_id, NULL::uuid
  FROM fluor_pairs fp
  JOIN _res_fluor rf ON rf.fluor_id=fp.fluor_id
  JOIN public.fluors fl ON fl.id=rf.fluor_id
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

-- tag-only → ensure a tag-only fusion exists
tag_pairs AS (
  SELECT DISTINCT p.id AS plasmid_id, rt.tag_id,
         (SELECT id FROM public.fusions WHERE tag_id=rt.tag_id AND fluor_id IS NULL LIMIT 1) AS fusion_id
  FROM _res_tag rt JOIN pl p ON p.code = rt.plasmid_code
),
ins_tag AS (
  INSERT INTO public.fusions (fusion_code, fusion_name, fluor_id, tag_id)
  SELECT DISTINCT
    'fus-'||encode(digest('tag:'||rt.tag_id::text,'sha256'),'hex'),
    tg.tag_name, NULL::uuid, rt.tag_id
  FROM tag_pairs tp
  JOIN _res_tag rt ON rt.tag_id=tp.tag_id
  JOIN public.tags tg ON tg.id=rt.tag_id
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

-- tag+fluor pair → ensure combined fusion exists
pair_pairs AS (
  SELECT DISTINCT p.id AS plasmid_id, rp.tag_id, rp.fluor_id,
         (SELECT id FROM public.fusions WHERE tag_id=rp.tag_id AND fluor_id=rp.fluor_id LIMIT 1) AS fusion_id
  FROM _res_pair rp JOIN pl p ON p.code = rp.plasmid_code
),
ins_pair AS (
  INSERT INTO public.fusions (fusion_code, fusion_name, fluor_id, tag_id)
  SELECT DISTINCT
    'fus-'||encode(digest('pair:'||rp.tag_id::text||':'||rp.fluor_id::text,'sha256'),'hex'),
    (SELECT tag_name FROM public.tags WHERE id=rp.tag_id) || '::' ||
    (SELECT fluor_name FROM public.fluors WHERE id=rp.fluor_id),
    rp.fluor_id, rp.tag_id
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
        """))

    # Ensure FT masters + ft_proteins from links
    with _eng().begin() as cx:
        cx.execute(text("""
            INSERT INTO public.treatments_fluorescent (ft_code, ft_text, created_by)
            SELECT s.ft_code, ''::text, 'plasmids-import'
            FROM (
              SELECT DISTINCT p.code AS ft_code
              FROM public.plasmids p
              JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
            ) s
            LEFT JOIN public.treatments_fluorescent t ON t.ft_code=s.ft_code
            WHERE t.ft_code IS NULL;

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