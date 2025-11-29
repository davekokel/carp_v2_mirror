# carp_app/ui/pages/090_📤_upload_plasmids_and_fusions.py
from __future__ import annotations

import io, math, pathlib, sys
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# Repo bootstrap
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine

# Auth / page
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()
st.set_page_config(page_title="CARP — Upload Plasmids & Fusions", page_icon="📤", layout="wide")
st.title("📤 Upload Plasmids & Plasmid Fusions")

_ENGINE: Engine | None = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

def _read_table(uploaded) -> pd.DataFrame:
    raw = io.BytesIO(uploaded.getvalue())
    if uploaded.name.lower().endswith(".xlsx"):
        xls = pd.ExcelFile(raw)
        sheet = st.selectbox("Worksheet", xls.sheet_names, index=0, key=f"sheet_{uploaded.name}")
        tmp = pd.read_excel(xls, sheet_name=sheet, header=0, dtype=object)
    else:
        tmp = pd.read_csv(raw, dtype=object)
    tmp = tmp.copy()
    tmp.columns = [str(c).strip().lower() for c in tmp.columns]
    return tmp

def _insert_rows(cx, table_name: str, rows: list[dict]):
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ", ".join([f":{c}" for c in cols])
    collist = ", ".join(cols)
    stmt = text(f"INSERT INTO {table_name} ({collist}) VALUES ({placeholders})")
    cx.execute(stmt, rows)

def _preview(df: pd.DataFrame, caption: str):
    st.caption(caption)
    st.dataframe(df.head(50), use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} rows")

tab1, tab2 = st.tabs(["① Plasmids", "② Plasmid Fusions"])

with tab1:
    st.subheader("Upload Plasmids")
    st.caption("CSV/XLSX headers: **plasmid_code,nickname,resistance,notes**. Extra columns are ignored.")
    up1 = st.file_uploader("Choose plasmids.csv", type=["csv", "xlsx"], key="plasmids_upl")
    if up1:
        df = _read_table(up1)
        # Map/normalize headers
        alias = {
            "plasmid_code": ["plasmid_code", "code", "plasmid", "plasmid_base_code"],
            "nickname":     ["nickname", "name", "plasmid_name", "title"],
            "resistance":   ["resistance", "antibiotic", "abx"],
            "notes":        ["notes", "note", "desc", "description"],
        }
        ren = {}
        for want, alts in alias.items():
            if want in df.columns: continue
            for a in alts:
                if a in df.columns:
                    ren[a] = want; break
        if ren:
            df = df.rename(columns=ren)
        need = {"plasmid_code"}
        missing = sorted(list(need - set(df.columns)))
        if missing:
            st.error("Missing required column(s): " + ", ".join(missing))
            st.stop()
        keep = [c for c in ["plasmid_code","nickname","resistance","notes"] if c in df.columns]
        df = df[keep].fillna("").astype(str)
        df["plasmid_code"] = df["plasmid_code"].str.strip()
        df = df[df["plasmid_code"] != ""]
        _preview(df, "Preview")

        if st.button("Process plasmids", type="primary", use_container_width=True, key="process_plasmids"):
            with _eng().begin() as cx:
                cx.execute(text("CREATE TEMP TABLE _stg_plasmids(plasmid_code text, nickname text, resistance text, notes text) ON COMMIT DROP"))
                rows = df.to_dict(orient="records")
                _insert_rows(cx, "_stg_plasmids", rows)
                cx.execute(text("""
                    UPDATE _stg_plasmids SET
                    plasmid_code = btrim(plasmid_code),
                    nickname     = NULLIF(btrim(COALESCE(nickname,'')),''),
                    resistance   = NULLIF(btrim(COALESCE(resistance,'')),''),
                    notes        = NULLIF(btrim(COALESCE(notes,'')),'');
                    DELETE FROM _stg_plasmids WHERE COALESCE(plasmid_code,'')='';
                """))

                # 1) ensure FK target rows exist (transgenes) for the incoming base codes
                cx.execute(text("""
                    INSERT INTO public.transgenes (transgene_base_code)
                    SELECT DISTINCT s.plasmid_code
                    FROM _stg_plasmids s
                    LEFT JOIN public.transgenes t
                    ON t.transgene_base_code = s.plasmid_code
                    WHERE t.transgene_base_code IS NULL
                """))

                # 2) upsert plasmids (FK now satisfied)
                res = cx.execute(text("""
                    WITH up AS (
                    INSERT INTO public.plasmids(code,nickname,resistance,notes)
                    SELECT plasmid_code, nickname, resistance, notes
                    FROM _stg_plasmids
                    ON CONFLICT (code) DO UPDATE SET
                        nickname   = COALESCE(EXCLUDED.nickname,  public.plasmids.nickname),
                        resistance = COALESCE(EXCLUDED.resistance, public.plasmids.resistance),
                        notes      = COALESCE(EXCLUDED.notes,      public.plasmids.notes)
                    RETURNING code AS plasmid_code, (xmax = 0) AS inserted
                    )
                    SELECT
                    SUM(CASE WHEN inserted THEN 1 ELSE 0 END) AS n_inserted,
                    SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END) AS n_updated
                    FROM up
                """)).mappings().first()

                n_ins = int(res["n_inserted"] or 0)
                n_upd = int(res["n_updated"] or 0)
                st.success(f"Plasmids — inserted: {n_ins} • updated: {n_upd}")

                touched = pd.read_sql(
                    text("""
                    SELECT code AS plasmid_code,
                            COALESCE(nickname,'')   AS nickname,
                            COALESCE(resistance,'') AS resistance,
                            COALESCE(notes,'')      AS notes
                    FROM public.plasmids
                    WHERE code = ANY(:codes)
                    ORDER BY code
                    """),
                    cx, params={"codes": df["plasmid_code"].tolist()}
                )
            st.subheader("Verification")
            st.dataframe(touched, use_container_width=True, hide_index=True)

# === REPLACE your entire Tab 2 "Plasmid Fusions" section with this ===
with tab2:
    st.subheader("Upload Plasmid Fusions")
    st.caption("CSV/XLSX headers: **plasmid_code,fluor,tag,tag_pos[,token]**. `tag` optional. If `tag` present, `tag_pos` must be `N` or `C`.")
    up2 = st.file_uploader("Choose plasmid_fusions.csv", type=["csv","xlsx"], key="fusions_upl")
    if up2:
        df = _read_table(up2)
        # map/normalize headers
        alias = {
            "plasmid_code": ["plasmid_code","code","plasmid","plasmid_base_code"],
            "fluor":        ["fluor","fluor_code","fluor_name","marker_fluor"],
            "tag":          ["tag","tag_code","tag_name","marker_tag"],
            "tag_pos":      ["tag_pos","pos","orientation","position"],
            "token":        ["token","original_token","raw_token"],  # optional
        }
        ren = {}
        for want, alts in alias.items():
            if want in df.columns: continue
            for a in alts:
                if a in df.columns:
                    ren[a] = want; break
        if ren:
            df = df.rename(columns=ren)

        need = {"plasmid_code","fluor"}
        missing = sorted(list(need - set(df.columns)))
        if missing:
            st.error("Missing required column(s): " + ", ".join(missing)); st.stop()

        for c in ["plasmid_code","fluor","tag","tag_pos","token"]:
            if c in df.columns:
                df[c] = df[c].fillna("").astype(str)
        df["plasmid_code"] = df["plasmid_code"].str.strip()
        df["fluor"]        = df["fluor"].str.strip()
        df["tag"]          = df["tag"].str.strip()
        df["tag_pos"]      = df["tag_pos"].str.strip().str.upper().map(lambda x: x if x in {"N","C"} else "")
        df = df[(df["plasmid_code"]!="") & (df["fluor"]!="")]

        _preview(df, "Preview")

        col1, col2 = st.columns([1,1])
        do_validate = col1.button("Validate only", type="secondary", use_container_width=True)
        do_process  = col2.button("Link fusions (upsert + link)", type="primary", use_container_width=True)

        if do_validate or do_process:
            with _eng().begin() as cx:
                # stage
                cx.execute(text("""
                    CREATE TEMP TABLE _stg_fusions(
                      plasmid_code text,
                      fluor        text,
                      tag          text,
                      tag_pos      text,
                      token        text
                    ) ON COMMIT DROP;
                """))
                allowed = ["plasmid_code","fluor","tag","tag_pos","token"]
                _insert_rows(cx, "_stg_fusions", df[[c for c in allowed if c in df.columns]].to_dict(orient="records"))
                cx.execute(text("""
                    UPDATE _stg_fusions SET
                      plasmid_code = btrim(plasmid_code),
                      fluor        = btrim(fluor),
                      tag          = NULLIF(btrim(COALESCE(tag,'')),''),
                      tag_pos      = NULLIF(upper(btrim(COALESCE(tag_pos,''))),''),
                      token        = NULLIF(btrim(COALESCE(token,'')),'');
                    DELETE FROM _stg_fusions WHERE COALESCE(plasmid_code,'')='' OR COALESCE(fluor,'')='';
                """))

                # validation
                bad_tagpos = pd.read_sql(text("""
                    SELECT * FROM _stg_fusions
                    WHERE tag IS NOT NULL AND tag <> '' AND tag_pos NOT IN ('N','C')
                """), cx)

                unresolved = pd.read_sql(text("""
                    WITH sym_flu AS (
                      SELECT lower(f.fluor_code) AS s FROM public.fluors f
                      UNION ALL SELECT lower(COALESCE(f.fluor_name,'')) FROM public.fluors f
                      UNION ALL SELECT ja.alias_norm FROM public.join_aliases ja
                        WHERE ja.target_kind='fluor'::public.alias_target_kind
                    ),
                    sym_tag AS (
                      SELECT lower(t.tag_code) AS s FROM public.tags t
                      UNION ALL SELECT lower(COALESCE(t.tag_name,'')) FROM public.tags t
                      UNION ALL SELECT ja.alias_norm FROM public.join_aliases ja
                        WHERE ja.target_kind='tag'::public.alias_target_kind
                    ),
                    norm AS (
                      SELECT plasmid_code, fluor, tag, tag_pos, token,
                             lower(fluor) AS fluor_sym,
                             CASE WHEN tag IS NULL OR tag='' THEN NULL ELSE lower(tag) END AS tag_sym
                      FROM _stg_fusions
                    )
                    SELECT plasmid_code, fluor, tag, tag_pos, token,
                      (fluor_sym NOT IN (SELECT s FROM sym_flu)) AS unresolved_fluor,
                      (tag IS NOT NULL AND tag <> '' AND (tag_sym NOT IN (SELECT s FROM sym_tag))) AS unresolved_tag,
                      (tag IS NOT NULL AND tag <> '' AND tag_pos IS NULL) AS missing_tag_pos
                    FROM norm
                    WHERE (fluor_sym NOT IN (SELECT s FROM sym_flu))
                       OR (tag IS NOT NULL AND tag <> '' AND (tag_sym NOT IN (SELECT s FROM sym_tag)))
                       OR (tag IS NOT NULL AND tag <> '' AND tag_pos IS NULL);
                """), cx)

                missing_plasmids = pd.read_sql(text("""
                    SELECT f.*
                    FROM _stg_fusions f
                    LEFT JOIN public.plasmids p ON p.code=f.plasmid_code
                    WHERE p.id IS NULL
                """), cx)

                if do_validate:
                    ok = (bad_tagpos.empty and unresolved.empty and missing_plasmids.empty)
                    if ok:
                        st.success("Validation passed: no unresolved rows.")
                    else:
                        if not bad_tagpos.empty:
                            st.error("Invalid tag_pos (must be N or C when tag present).")
                            st.dataframe(bad_tagpos, use_container_width=True, hide_index=True)
                        if not unresolved.empty:
                            st.error("Unresolved symbols or missing tag_pos.")
                            st.dataframe(unresolved, use_container_width=True, hide_index=True)
                        if not missing_plasmids.empty:
                            st.error("Plasmid codes not found in public.plasmids.")
                            st.dataframe(missing_plasmids, use_container_width=True, hide_index=True)

                if do_process:
                    if not bad_tagpos.empty or not unresolved.empty or not missing_plasmids.empty:
                        st.error("Cannot process: fix validation errors and re-run Validate.")
                        st.stop()

                    # link using resolver (same connection as staging; temp table visible)
                    cx.execute(text("""
                      INSERT INTO public.join_plasmid_fusions(plasmid_id, fusion_id)
                      SELECT DISTINCT p.id,
                             public.ensure_fusion_id(f.fluor, NULLIF(f.tag,''), NULLIF(f.tag_pos,''))
                      FROM _stg_fusions f
                      JOIN public.plasmids p ON p.code = f.plasmid_code
                      WHERE public.ensure_fusion_id(f.fluor, NULLIF(f.tag,''), NULLIF(f.tag_pos,'')) IS NOT NULL
                      ON CONFLICT DO NOTHING;
                    """))

                    res_counts = cx.execute(text("""
                      SELECT
                        (SELECT COUNT(*) FROM _stg_fusions) AS n_rows,
                        (SELECT COUNT(*) FROM public.join_plasmid_fusions j
                           JOIN public.plasmids p ON p.id=j.plasmid_id
                           WHERE p.code = ANY(:codes)) AS n_links
                    """), {"codes": df["plasmid_code"].unique().tolist()}).mappings().first()

                    st.success(
                        f"Linked fusions • rows: {int(res_counts['n_rows'] or 0)} • "
                        f"links present (for uploaded plasmids): {int(res_counts['n_links'] or 0)}"
                    )

                    detail = pd.read_sql(text("""
                        SELECT p.code AS plasmid_code,
                               COALESCE(fl.fluor_name, fl.fluor_code, '') AS fluor,
                               COALESCE(tg.tag_name, tg.tag_code, '')     AS tag,
                               COALESCE(f.tag_pos::text,'')               AS tag_pos
                        FROM public.plasmids p
                        JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id=p.id
                        JOIN public.fusions f               ON f.id=jpf.fusion_id
                        LEFT JOIN public.fluors fl          ON fl.id=f.fluor_id
                        LEFT JOIN public.tags   tg          ON tg.id=f.tag_id
                        WHERE p.code = ANY(:codes)
                        ORDER BY p.code, fluor, tag, tag_pos
                    """), cx, params={"codes": df["plasmid_code"].unique().tolist()})

                    st.subheader("Verification (Plasmid → Fusion links)")
                    st.dataframe(detail, use_container_width=True, hide_index=True)