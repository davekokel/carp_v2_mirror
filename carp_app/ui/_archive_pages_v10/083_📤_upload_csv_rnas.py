# carp_app/ui/pages/095_📤_upload_rnas_and_fusions.py
from __future__ import annotations

import io, pathlib, sys
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
from carp_app.ui.lib.page_engine import engine as _engine

# ── Auth / Page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()
st.set_page_config(page_title="CARP — Upload RNAs & RNA Fusions", page_icon="📤", layout="wide")
st.title("📤 Upload RNAs & RNA Fusions")

@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    return _engine()

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
    cx.execute(text(f"INSERT INTO {table_name} ({collist}) VALUES ({placeholders})"), rows)

def _preview(df: pd.DataFrame, caption: str):
    st.caption(caption)
    st.dataframe(df.head(50), use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} rows")

tab1, tab2 = st.tabs(["① RNAs", "② RNA Fusions"])

# ─────────────────────────────────────────────────────────────────────────────
# Tab 1: RNAs (base rows only)
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Upload RNAs")
    st.caption("CSV/XLSX headers: **rna_code** (or **rna_base_code** to derive), optional: **rna_name** (→ nickname), **notes**.")
    up1 = st.file_uploader("Choose rnas.csv", type=["csv","xlsx"], key="rnas_upl")
    if up1:
        df = _read_table(up1)
        # Header aliases
        alias = {
            "rna_code":      ["rna_code","code","id"],
            "rna_base_code": ["rna_base_code","base_plasmid_code","plasmid_code","base_code"],
            "rna_name":      ["rna_name","nickname","name","title"],
            "notes":         ["notes","note","desc","description"],
        }
        ren = {}
        for want, alts in alias.items():
            if want in df.columns: continue
            for a in alts:
                if a in df.columns:
                    ren[a] = want; break
        if ren:
            df = df.rename(columns=ren)
        for c in ["rna_code","rna_base_code","rna_name","notes"]:
            if c in df.columns:
                df[c] = df[c].fillna("").astype(str)
        # Derive rna_code if missing but base exists
        if "rna_code" not in df.columns:
            df["rna_code"] = ""
        if "rna_base_code" in df.columns:
            df["rna_code"] = df.apply(
                lambda r: (r["rna_code"].strip() or (f"RNA({r['rna_base_code'].strip()})" if str(r["rna_base_code"]).strip() else "")),
                axis=1
            )
        df["rna_code"] = df["rna_code"].str.strip()
        df = df[df["rna_code"] != ""]
        keep = [c for c in ["rna_code","rna_name","notes"] if c in df.columns]
        df = df[keep]
        _preview(df, "Preview")

        if st.button("Process RNAs", type="primary", use_container_width=True, key="process_rnas"):
            with _eng().begin() as cx:
                cx.execute(text("""
                    CREATE TEMP TABLE _stg_rnas(
                      rna_code text,
                      rna_name text,
                      notes    text
                    ) ON COMMIT DROP;
                """))
                # normalize to stg layout
                stg = df.rename(columns={"rna_name":"nickname"}) \
                        .rename(columns={"nickname":"rna_name"})  # ensure key exists
                stg = stg.rename(columns={"rna_name":"rna_name", "notes":"notes"})
                _insert_rows(cx, "_stg_rnas",
                             [{"rna_code": r.get("rna_code",""),
                               "rna_name": r.get("rna_name",""),
                               "notes":    r.get("notes","")} for r in df.to_dict(orient="records")])

                cx.execute(text("""
                    UPDATE _stg_rnas SET
                      rna_code = btrim(rna_code),
                      rna_name = NULLIF(btrim(COALESCE(rna_name,'')),''),
                      notes    = NULLIF(btrim(COALESCE(notes,'')),'');
                    DELETE FROM _stg_rnas WHERE COALESCE(rna_code,'')='';
                """))

                res = cx.execute(text("""
                    WITH up AS (
                      INSERT INTO public.rnas(rna_code, nickname, notes)
                      SELECT rna_code, rna_name, notes
                      FROM _stg_rnas
                      ON CONFLICT (rna_code) DO UPDATE SET
                        nickname = COALESCE(EXCLUDED.nickname, public.rnas.nickname),
                        notes    = COALESCE(EXCLUDED.notes,    public.rnas.notes)
                      RETURNING rna_code, (xmax = 0) AS inserted
                    )
                    SELECT
                      SUM(CASE WHEN inserted THEN 1 ELSE 0 END) AS n_inserted,
                      SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END) AS n_updated
                    FROM up
                """)).mappings().first()

                st.success(f"RNAs — inserted: {int(res['n_inserted'] or 0)} • updated: {int(res['n_updated'] or 0)}")

                touched = pd.read_sql(
                    text("""
                      SELECT rna_code, COALESCE(nickname,'') AS nickname, COALESCE(notes,'') AS notes
                      FROM public.rnas WHERE rna_code = ANY(:codes) ORDER BY rna_code
                    """),
                    cx, params={"codes": df["rna_code"].tolist()}
                )
            st.subheader("Verification")
            st.dataframe(touched, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# Tab 2: RNA Fusions (one fusion per row)
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Upload RNA Fusions")
    st.caption("CSV/XLSX headers: **rna_code,fluor,tag,tag_pos[,token]**. `tag` optional. If `tag` present, `tag_pos` must be `N` or `C`.")
    up2 = st.file_uploader("Choose rna_fusions.csv", type=["csv","xlsx"], key="rnaf_upl")
    if up2:
        df = _read_table(up2)
        alias = {
            "rna_code": ["rna_code","code","id"],
            "fluor":    ["fluor","fluor_code","fluor_name","marker_fluor"],
            "tag":      ["tag","tag_code","tag_name","marker_tag"],
            "tag_pos":  ["tag_pos","pos","orientation","position"],
            "token":    ["token","original_token","raw_token"],
        }
        ren = {}
        for want, alts in alias.items():
            if want in df.columns: continue
            for a in alts:
                if a in df.columns:
                    ren[a] = want; break
        if ren:
            df = df.rename(columns=ren)

        need = {"rna_code","fluor"}
        missing = sorted(list(need - set(df.columns)))
        if missing:
            st.error("Missing required column(s): " + ", ".join(missing)); st.stop()

        for c in ["rna_code","fluor","tag","tag_pos","token"]:
            if c in df.columns:
                df[c] = df[c].fillna("").astype(str)
        df["rna_code"] = df["rna_code"].str.strip()
        df["fluor"]    = df["fluor"].str.strip()
        df["tag"]      = df["tag"].str.strip()
        df["tag_pos"]  = df["tag_pos"].str.strip().str.upper().map(lambda x: x if x in {"N","C"} else "")
        df = df[(df["rna_code"]!="") & (df["fluor"]!="")]

        _preview(df, "Preview")

        c1, c2 = st.columns([1,1])
        do_validate = c1.button("Validate only", type="secondary", use_container_width=True)
        do_process  = c2.button("Link RNA fusions (upsert + link)", type="primary", use_container_width=True)

        if do_validate or do_process:
            with _eng().begin() as cx:
                # Staging table
                cx.execute(text("""
                    CREATE TEMP TABLE _stg_rna_fusions(
                      rna_code text,
                      fluor    text,
                      tag      text,
                      tag_pos  text,
                      token    text
                    ) ON COMMIT DROP;
                """))
                allowed = ["rna_code","fluor","tag","tag_pos","token"]
                _insert_rows(cx, "_stg_rna_fusions", df[[c for c in allowed if c in df.columns]].to_dict(orient="records"))

                # Normalize
                cx.execute(text("""
                    UPDATE _stg_rna_fusions SET
                      rna_code = btrim(rna_code),
                      fluor    = btrim(fluor),
                      tag      = NULLIF(btrim(COALESCE(tag,'')),''),
                      tag_pos  = NULLIF(upper(btrim(COALESCE(tag_pos,''))),''),
                      token    = NULLIF(btrim(COALESCE(token,'')),'');
                    DELETE FROM _stg_rna_fusions WHERE COALESCE(rna_code,'')='' OR COALESCE(fluor,'')='';
                """))

                # Validation: tag_pos must be N/C when tag present
                bad_tagpos = pd.read_sql(text("""
                    SELECT * FROM _stg_rna_fusions
                    WHERE tag IS NOT NULL AND tag <> '' AND tag_pos NOT IN ('N','C')
                """), cx)

                # Validation: unresolved symbols (via catalogs + join_aliases)
                unresolved = pd.read_sql(text("""
                    WITH sym_flu AS (
                      SELECT lower(f.fluor_code) AS s FROM public.fluors f
                      UNION ALL SELECT lower(COALESCE(f.fluor_name,'')) FROM public.fluors f
                      UNION ALL SELECT alias_norm FROM public.join_aliases
                        WHERE target_kind='fluor'::public.alias_target_kind
                    ),
                    sym_tag AS (
                      SELECT lower(t.tag_code) AS s FROM public.tags t
                      UNION ALL SELECT lower(COALESCE(t.tag_name,'')) FROM public.tags t
                      UNION ALL SELECT alias_norm FROM public.join_aliases
                        WHERE target_kind='tag'::public.alias_target_kind
                    ),
                    norm AS (
                      SELECT rna_code, fluor, tag, tag_pos, token,
                             lower(fluor) AS fluor_sym,
                             CASE WHEN tag IS NULL OR tag='' THEN NULL ELSE lower(tag) END AS tag_sym
                      FROM _stg_rna_fusions
                    )
                    SELECT rna_code, fluor, tag, tag_pos, token,
                      (fluor_sym NOT IN (SELECT s FROM sym_flu)) AS unresolved_fluor,
                      (tag IS NOT NULL AND tag <> '' AND (tag_sym NOT IN (SELECT s FROM sym_tag))) AS unresolved_tag,
                      (tag IS NOT NULL AND tag <> '' AND tag_pos IS NULL) AS missing_tag_pos
                    FROM norm
                    WHERE (fluor_sym NOT IN (SELECT s FROM sym_flu))
                       OR (tag IS NOT NULL AND tag <> '' AND (tag_sym NOT IN (SELECT s FROM sym_tag)))
                       OR (tag IS NOT NULL AND tag <> '' AND tag_pos IS NULL);
                """), cx)

                # Validation: missing RNAs
                missing_rnas = pd.read_sql(text("""
                    SELECT rf.*
                    FROM _stg_rna_fusions rf
                    LEFT JOIN public.rnas r ON r.rna_code=rf.rna_code
                    WHERE r.id IS NULL
                """), cx)

                if do_validate:
                    ok = (bad_tagpos.empty and unresolved.empty and missing_rnas.empty)
                    if ok:
                        st.success("Validation passed: no unresolved rows.")
                    else:
                        if not bad_tagpos.empty:
                            st.error("Invalid tag_pos (must be N or C when tag present).")
                            st.dataframe(bad_tagpos, use_container_width=True, hide_index=True)
                        if not unresolved.empty:
                            st.error("Unresolved symbols or missing tag_pos.")
                            st.dataframe(unresolved, use_container_width=True, hide_index=True)
                        if not missing_rnas.empty:
                            st.error("RNA codes not found in public.rnas.")
                            st.dataframe(missing_rnas, use_container_width=True, hide_index=True)

                if do_process:
                    if not bad_tagpos.empty or not unresolved.empty or not missing_rnas.empty:
                        st.error("Cannot process: fix validation errors and re-run Validate.")
                        st.stop()

                    # ---- SIMPLE LINKING via helper: ensure_fusion_id(fluor, tag, tag_pos) ----
                    cx.execute(text("""
                      INSERT INTO public.join_rna_fusions(rna_id, fusion_id)
                      SELECT DISTINCT r.id,
                             public.ensure_fusion_id(f.fluor, NULLIF(f.tag,''), NULLIF(f.tag_pos,''))
                      FROM _stg_rna_fusions f
                      JOIN public.rnas r ON r.rna_code = f.rna_code
                      WHERE public.ensure_fusion_id(f.fluor, NULLIF(f.tag,''), NULLIF(f.tag_pos,'')) IS NOT NULL
                      ON CONFLICT DO NOTHING;
                    """))

                    # Counts for UI
                    res_counts = cx.execute(text("""
                      SELECT
                        (SELECT COUNT(*) FROM _stg_rna_fusions) AS n_rows,
                        (SELECT COUNT(*) FROM public.join_rna_fusions j
                           JOIN public.rnas r ON r.id=j.rna_id
                           WHERE r.rna_code = ANY(:codes)) AS n_links
                    """), {"codes": df["rna_code"].unique().tolist()}).mappings().first()

                    st.success(
                        f"Linked RNA fusions • rows: {int(res_counts['n_rows'] or 0)} • "
                        f"links present (for uploaded RNAs): {int(res_counts['n_links'] or 0)}"
                    )

                    # Verification grid
                    detail = pd.read_sql(text("""
                        SELECT r.rna_code,
                               COALESCE(fl.fluor_name, fl.fluor_code, '') AS fluor,
                               COALESCE(tg.tag_name, tg.tag_code, '')     AS tag,
                               COALESCE(f.tag_pos::text,'')               AS tag_pos
                        FROM public.rnas r
                        JOIN public.join_rna_fusions jrf ON jrf.rna_id=r.id
                        JOIN public.fusions f           ON f.id=jrf.fusion_id
                        LEFT JOIN public.fluors fl      ON fl.id=f.fluor_id
                        LEFT JOIN public.tags   tg      ON tg.id=f.tag_id
                        WHERE r.rna_code = ANY(:codes)
                        ORDER BY r.rna_code, fluor, tag, tag_pos
                    """), cx, params={"codes": df["rna_code"].unique().tolist()})

                    st.subheader("Verification (RNA → Fusion links)")
                    st.dataframe(detail, use_container_width=True, hide_index=True)