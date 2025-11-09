# carp_app/ui/pages/095_📤_upload_csv_rnas.py
from __future__ import annotations

import io, os, pathlib, re, sys
from typing import Optional, List, Dict
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

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

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Upload RNAs from CSV", page_icon="📤", layout="wide")
st.title("CARP — Upload RNAs from CSV (v6)")
st.caption(
    "CSV/XLSX must include **rna_base_code**. Optional: **rna_name** (stored as nickname), **notes**. "
    "Markers in **token_list** accept `Fluor` or `Fluor::Tag` (also `:`, `/`, `@`, `+`). "
    "If `rna_code` is blank, it becomes `RNA(<rna_base_code>)`. "
    "Markers are linked via **join_rna_fusions**. Fluor-only tokens are allowed."
)

@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL","")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _engine()

def _read_upload(uploaded) -> pd.DataFrame:
    raw = io.BytesIO(uploaded.getvalue())
    fname = (uploaded.name or "").lower()
    if fname.endswith(".xlsx"):
        xls = pd.ExcelFile(raw)
        sheet = st.selectbox("Worksheet", xls.sheet_names, index=0)
        df = pd.read_excel(xls, sheet_name=sheet, dtype=object)
    else:
        df = pd.read_csv(raw, dtype=object)
    return df

uploaded = st.file_uploader("Upload RNAs (.csv or .xlsx)", type=["csv","xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin."); st.stop()

creator = getattr(user, "email", None) or os.environ.get("USER") or ""

try:
    df = _read_upload(uploaded)
except Exception as e:
    st.error(f"Failed to read file: {e}"); st.stop()

df.columns = [str(c).strip().lower() for c in df.columns]
ALIASES: Dict[str, List[str]] = {
    "rna_base_code": ["rna_base_code","base_plasmid_code","plasmid_code","base_code"],
    "rna_name":      ["rna_name","nickname","name","title"],
    "notes":         ["notes","note","desc","description"],
    "token_list":    ["token_list","fusion_tokens","fluor_or_fluor_fusion_name","fusion_name","fluors","fusions","fluor_list","marker_list","tokens"],
    "rna_code":      ["rna_code","code","id"],
}
ren: Dict[str, str] = {}
for tgt, alts in ALIASES.items():
    if tgt in df.columns: continue
    for a in alts:
        if a in df.columns: ren[a] = tgt; break
if ren:
    df.rename(columns=ren, inplace=True)

if "rna_base_code" not in df.columns:
    st.error("Missing required column: rna_base_code"); st.stop()

for c in ("rna_base_code","rna_name","notes","token_list","rna_code"):
    if c in df.columns:
        df[c] = df[c].fillna("").astype(str)

if "rna_code" not in df.columns:
    df["rna_code"] = ""
df["rna_code"] = df.apply(lambda r: (r["rna_code"].strip() or f"RNA({str(r['rna_base_code']).strip()})"), axis=1)

if "token_list" not in df.columns:
    if "rna_name" in df.columns and df["rna_name"].str.contains(r"::|[:/@+]", regex=True).any():
        df["token_list"] = df["rna_name"]
    else:
        df["token_list"] = ""

st.subheader("Preview (first 50)")
preview_cols = [c for c in ["rna_base_code","rna_code","rna_name","notes","token_list"] if c in df.columns]
st.dataframe(df[preview_cols].head(50), use_container_width=True, hide_index=True)

DELIM_INNER = re.compile(r"::|[:/@+]")
def _split_token(tok: str) -> List[str]:
    return [p.strip() for p in DELIM_INNER.split((tok or "").strip()) if p.strip()]

def _load_catalogs(cx) -> tuple[set, set]:
    flu_sql = text("""
      WITH u AS (
        SELECT lower(fluor_code) AS sym FROM public.fluors
        UNION ALL SELECT lower(COALESCE(fluor_name,'')) FROM public.fluors
        UNION ALL SELECT alias_norm FROM public.join_aliases
          WHERE target_kind='fluor'::alias_target_kind
      )
      SELECT DISTINCT sym FROM u WHERE sym <> ''
    """)
    tag_sql = text("""
      WITH u AS (
        SELECT lower(tag_code) AS sym FROM public.tags
        UNION ALL SELECT lower(COALESCE(tag_name,'')) FROM public.tags
        UNION ALL SELECT alias_norm FROM public.join_aliases
          WHERE target_kind='tag'::alias_target_kind
      )
      SELECT DISTINCT sym FROM u WHERE sym <> ''
    """)
    flu_set = set(pd.read_sql(flu_sql, cx)["sym"].dropna().tolist())
    tag_set = set(pd.read_sql(tag_sql, cx)["sym"].dropna().tolist())
    return flu_set, tag_set

def _classify(parts, flu_set, tag_set):
    if not parts:
        return None, None, None
    if len(parts) == 1:
        f = parts[0].lower()
        return (parts[0], None, None) if f in flu_set else (None, None, 'unresolved_fluor')
    l, r = parts[0].lower(), parts[-1].lower()
    Lf, Rf = l in flu_set, r in flu_set
    Lt, Rt = l in tag_set, r in tag_set
    if Lf and (Rt or r == ''):
        return (parts[0], parts[-1] if Rt else None, None)
    if Rf and (Lt or l == ''):
        return (parts[-1], parts[0] if Lt else None, None)
    if (Lf and Rf) or (Lt and Rt):
        return (None, None, 'ambiguous')
    if not Lf and not Rf:
        return (None, None, 'unresolved_fluor')
    return (parts[0] if Lf else parts[-1], None, 'unresolved_tag')

def _resolve_name_to_id(cx, kind: str, sym: str) -> Optional[int]:
    if kind == "fluor":
        q = text("""
          SELECT id FROM public.fluors
          WHERE lower(fluor_code)=lower(:s) OR lower(COALESCE(fluor_name,''))=lower(:s)
          UNION
          SELECT target_id FROM public.join_aliases
          WHERE target_kind='fluor'::alias_target_kind AND alias_norm=lower(:s)
          LIMIT 1
        """)
    else:
        q = text("""
          SELECT id FROM public.tags
          WHERE lower(tag_code)=lower(:s) OR lower(COALESCE(tag_name,''))=lower(:s)
          UNION
          SELECT target_id FROM public.join_aliases
          WHERE target_kind='tag'::alias_target_kind AND alias_norm=lower(:s)
          LIMIT 1
        """)
    rec = cx.execute(q, {"s": sym}).first()
    return None if rec is None else rec[0]

def _get_or_create_fusion_id(cx, fluor_sym: str, tag_sym: Optional[str]) -> Optional[int]:
    fid = _resolve_name_to_id(cx, "fluor", fluor_sym)
    if not fid:
        return None
    tid = None
    if tag_sym:
        tid = _resolve_name_to_id(cx, "tag", tag_sym)
        if tag_sym and not tid:
            return None

    sel = text("""
      SELECT id
      FROM public.fusions
      WHERE fluor_id = :fid
        AND ((:tid IS NULL AND tag_id IS NULL) OR tag_id = :tid)
      LIMIT 1
    """)
    rec = cx.execute(sel, {"fid": fid, "tid": tid}).first()
    if rec:
        return rec[0]

    cx.execute(
      text("""
        INSERT INTO public.fusions(fluor_id, tag_id)
        VALUES (:fid, :tid)
        ON CONFLICT DO NOTHING
      """),
      {"fid": fid, "tid": tid}
    )

    rec = cx.execute(sel, {"fid": fid, "tid": tid}).first()
    return None if rec is None else rec[0]

tokens_raw: List[str] = []
if "token_list" in df.columns:
    for raw in df["token_list"].fillna(""):
        tokens_raw.extend([t.strip() for t in str(raw).split("|") if str(t).strip()])

unres_flu, ambig = [], []
flu_set: set[str] = set(); tag_set: set[str] = set()
has_any_tokens = len(tokens_raw) > 0
if has_any_tokens:
    with _eng().begin() as cx:
        flu_set, tag_set = _load_catalogs(cx)
    for tok in tokens_raw:
        parts = _split_token(tok)
        fluor, tag, err = _classify(parts, flu_set, tag_set)
        if err == 'unresolved_fluor': unres_flu.append(tok)
        elif err == 'ambiguous':       ambig.append(tok)

if unres_flu or ambig:
    col1, col2 = st.columns(2)
    if unres_flu:
        with col1:
            st.error(f"{len(set(unres_flu))} unknown fluor token(s). Add to public.fluors or fix the CSV.")
            st.dataframe(pd.DataFrame({"unresolved_fluor_token": sorted(set(unres_flu))}), use_container_width=True, hide_index=True)
    if ambig:
        with col2:
            st.error(f"{len(set(ambig))} ambiguous token(s). Fix the CSV.")
            st.dataframe(pd.DataFrame({"ambiguous_token": sorted(set(ambig))}), use_container_width=True, hide_index=True)
    st.stop()

inserted, updated, linked = [], [], []

if st.button("Process RNA upload", type="primary", use_container_width=True):
    with _eng().begin() as cx:
        for _, r in df.iterrows():
            base = (r.get("rna_base_code") or "").strip()
            rc   = (r.get("rna_code")      or "").strip()
            rn   = (r.get("rna_name")      or "").strip() or None
            nt   = (r.get("notes")         or "").strip() or None
            tok  = (r.get("token_list")    or "").strip()

            if not base:
                st.error("Row missing rna_base_code."); st.stop()
            if not rc:
                st.error("Row missing rna_code after normalization."); st.stop()

            row = cx.execute(
                text("""
                  INSERT INTO public.rnas (rna_code, nickname, notes)
                  VALUES (:c, :n, :no)
                  ON CONFLICT (rna_code) DO UPDATE
                    SET nickname = COALESCE(EXCLUDED.nickname, public.rnas.nickname),
                        notes    = COALESCE(EXCLUDED.notes,    public.rnas.notes)
                  RETURNING id, (xmax::text <> '0') AS was_update
                """),
                {"c": rc, "n": rn, "no": nt}
            ).mappings().first()
            rna_id = row["id"]
            (updated if row["was_update"] else inserted).append(rc)

            if tok:
                for raw_tok in [t.strip() for t in tok.split("|") if t.strip()]:
                    parts = _split_token(raw_tok)
                    fluor, tag, err = _classify(parts, flu_set, tag_set) if has_any_tokens else (None, None, None)
                    if not fluor or err in ('unresolved_fluor','ambiguous'):
                        continue
                    fusion_id = _get_or_create_fusion_id(cx, fluor, tag)  # tag may be None
                    if fusion_id:
                        cx.execute(
                            text("""
                              INSERT INTO public.join_rna_fusions (rna_id, fusion_id)
                              VALUES (:rid, :fid)
                              ON CONFLICT DO NOTHING
                            """),
                            {"rid": rna_id, "fid": fusion_id}
                        )
                        linked.append({"rna_code": rc, "token": raw_tok})

    st.success(f"Uploaded RNAs • inserted: {len(inserted)} • updated: {len(updated)} • linked: {len(linked)}")

    with _eng().begin() as cx:
        v = pd.read_sql(
            text("""
              SELECT
                r.rna_code,
                COALESCE(r.nickname,'') AS nickname,
                COALESCE(r.notes,'')    AS notes,
                COALESCE(v.fluors,'')   AS fluors,
                COALESCE(v.tags,'')     AS tags,
                r.created_at
              FROM public.rnas r
              LEFT JOIN public.v_rnas v ON v.rna_code = r.rna_code
              WHERE r.rna_code = ANY(:codes)
              ORDER BY r.rna_code
            """),
            cx, params={"codes": [*inserted, *updated]}
        )
    if not v.empty:
        st.subheader("Verification (v_rnas)")
        st.dataframe(v, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇︎ Download verification CSV",
            data=v.to_csv(index=False).encode("utf-8"),
            file_name="rnas_verification.csv",
            type="secondary"
        )