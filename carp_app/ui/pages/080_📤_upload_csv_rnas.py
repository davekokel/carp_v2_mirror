# carp_app/ui/pages/095_📤_upload_csv_rnas.py
from __future__ import annotations

import sys, pathlib, io, os, re, math
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
st.title("CARP — Upload RNAs from CSV")
st.caption(
    "CSV must include **plasmid_code**. Optional: **nickname** (RNA name), **notes**, "
    "**fluor_or_fluor_fusion_name** (pipe-delimited tokens like `Fluor` or `Tag:Fluor` / `Tag::Fluor`). "
    "We generate **rna_code = RNA(plasmid_code)**. If tokens are present, we strictly resolve them and "
    "seed plasmid→fusion links for the base plasmid."
)

@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL","")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _engine()

def _read_upload(uploaded) -> pd.DataFrame:
    raw = io.BytesIO(uploaded.getvalue())
    name = (uploaded.name or "").lower()
    if name.endswith(".xlsx"):
        xls = pd.ExcelFile(raw)
        sheet = st.selectbox("Worksheet", xls.sheet_names, index=0)
        df = pd.read_excel(xls, sheet_name=sheet, dtype=object)
    else:
        df = pd.read_csv(raw, dtype=object)
    df = df.replace({float("nan"): None})
    return df

uploaded = st.file_uploader("Upload RNAs (.csv or .xlsx)", type=["csv","xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin."); st.stop()

creator = getattr(user, "email", None) or os.environ.get("USER") or ""

try:
    df = _read_upload(uploaded)
except Exception as e:
    st.error(f"Failed to read file: {e}"); st.stop()

# Normalize headers & aliases for your CSV columns
df.columns = [str(c).strip().lower() for c in df.columns]
ALIASES: Dict[str, List[str]] = {
    "base_plasmid_code": ["plasmid_code","base_plasmid_code","base_code"],
    "rna_name":          ["nickname","rna_name","name","title"],
    "notes":             ["notes","note","desc","description"],
    "token_list":        ["fluor_or_fluor_fusion_name","fusion_name","fluors","fusions","fluor_list"],
}
rename: Dict[str,str] = {}
for target, alts in ALIASES.items():
    if target in df.columns: continue
    for a in alts:
        if a in df.columns:
            rename[a] = target
            break
if rename:
    df.rename(columns=rename, inplace=True)

# Required
if "base_plasmid_code" not in df.columns:
    st.error("Missing required column: plasmid_code"); st.stop()

# Coerce/clean
for c in ("base_plasmid_code","rna_name","notes","token_list"):
    if c in df.columns:
        df[c] = df[c].fillna("").astype(str)

# Generate rna_code = RNA(plasmid_code)
df["rna_code"] = df["base_plasmid_code"].map(lambda b: f"RNA({str(b).strip()})" if str(b).strip() else "")

# Preflight 1: base plasmids must exist
base_codes = sorted(set([str(x).strip() for x in df["base_plasmid_code"].tolist() if str(x).strip()]))
with _eng().begin() as cx:
    existing = pd.read_sql(text("SELECT code FROM public.plasmids WHERE code = ANY(:codes)"),
                           cx, params={"codes": base_codes})
known = set(existing["code"].tolist()) if not existing.empty else set()
unknown = [b for b in base_codes if b not in known]
if unknown:
    st.error("Unknown plasmid_code value(s) not found in plasmids: " + ", ".join(unknown))
    st.stop()

# STRICT token preflight (if token_list present): validate via resolver catalogs
# We’ll reuse the same logic as plasmids upload: accept Tag:Fluor, Fluor:Tag, or Fluor
def _split_token(tok: str) -> List[str]:
    # treat '::' as two separators as well
    return [p.strip() for p in re.split(r"[:/@+]", (tok or "").strip()) if p.strip()]

def _load_catalogs(cx) -> tuple[set, set]:
    flu_set: set[str] = set()
    rows = pd.read_sql(
        text("""
          SELECT
            lower(fluor_code) AS code_lc,
            lower(COALESCE(fluor_name,'')) AS name_lc,
            lower(COALESCE(
              CASE
                WHEN pg_typeof(alt_names)::text = 'text[]' THEN array_to_string(alt_names, ';')
                ELSE alt_names::text
              END,'')
            ) AS aliases_lc
          FROM public.fluors
        """), cx)
    for _, r in rows.iterrows():
        if r["code_lc"]: flu_set.add(r["code_lc"])
        if r["name_lc"]: flu_set.add(r["name_lc"])
        a = (r["aliases_lc"] or "").strip()
        if a:
            for alias in re.split(r"[;,\|]", a):
                alias = alias.strip().lower()
                if alias: flu_set.add(alias)

    tag_set: set[str] = set()
    rows2 = pd.read_sql(text("SELECT lower(tag_code) AS code_lc, lower(COALESCE(tag_name,'')) AS name_lc FROM public.tags"), cx)
    for _, r in rows2.iterrows():
        if r["code_lc"]: tag_set.add(r["code_lc"])
        if r["name_lc"]: tag_set.add(r["name_lc"])
    return flu_set, tag_set

def _classify(parts: List[str], flu_set: set, tag_set: set) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not parts: return None, None, None
    if len(parts) == 1:
        f = parts[0].lower()
        return (parts[0], None, None) if f in flu_set else (None, None, 'unresolved_fluor')
    left, right = parts[0].lower(), parts[-1].lower()
    Lf, Rf = left in flu_set, right in flu_set
    Lt, Rt = left in tag_set, right in tag_set
    if Lf and (Rt or right==''): return (parts[0], parts[-1] if Rt else None, None)
    if Rf and (Lt or left==''):  return (parts[-1], parts[0] if Lt else None, None)
    if (Lf and Rf) or (Lt and Rt): return (None, None, 'ambiguous')
    if not Lf and not Rf: return (None, None, 'unresolved_fluor')
    return (parts[0] if Lf else parts[-1], None, 'unresolved_tag')

unresolved_fluors, unresolved_tags, ambiguous = [], [], []
if "token_list" in df.columns:
    tokens_raw: List[str] = []
    for raw in df["token_list"].fillna(""):
        tokens_raw.extend([t.strip() for t in str(raw).split("|") if str(t).strip()])
    if tokens_raw:
        with _eng().begin() as cx:
            flu_set, tag_set = _load_catalogs(cx)
        for tok in tokens_raw:
            parts = _split_token(tok)
            fluor, tag, err = _classify(parts, flu_set, tag_set)
            if err == 'unresolved_fluor': unresolved_fluors.append(tok)
            elif err == 'unresolved_tag': unresolved_tags.append(tok)
            elif err == 'ambiguous': ambiguous.append(tok)

if unresolved_fluors or unresolved_tags or ambiguous:
    if unresolved_fluors:
        st.error(f"{len(unresolved_fluors)} unknown fluor token(s). Add to public.fluors or fix the CSV.")
        st.dataframe(pd.DataFrame({"unresolved_fluor_token": sorted(set(unresolved_fluors))}), hide_index=True, width="stretch")
    if unresolved_tags:
        st.error(f"{len(unresolved_tags)} unknown tag token(s). Add to public.tags or fix the CSV.")
        st.dataframe(pd.DataFrame({"unresolved_tag_token": sorted(set(unresolved_tags))}), hide_index=True, width="stretch")
    if ambiguous:
        st.error(f"{len(ambiguous)} ambiguous token(s). Fix the CSV.")
        st.dataframe(pd.DataFrame({"ambiguous_token": sorted(set(ambiguous))}), hide_index=True, width="stretch")
    st.stop()

# Preview
st.subheader("Preview (first 50)")
prev = df[["base_plasmid_code","rna_code","rna_name","notes","token_list"]].copy()
prev.rename(columns={
    "base_plasmid_code":"plasmid_code",
    "rna_name":"nickname",
    "token_list":"fluor_or_fluor_fusion_name",
}, inplace=True)
st.dataframe(prev.head(50), width="stretch", hide_index=True)

inserted, updated, seeded_tokens = [], [], []

if st.button("Process RNA upload", type="primary", use_container_width=True):
    with _eng().begin() as cx:
        for _, r in df.iterrows():
            base = (r.get("base_plasmid_code") or "").strip()
            rc   = (r.get("rna_code") or "").strip()
            rn   = (r.get("rna_name") or "").strip() or None
            nt   = (r.get("notes") or "").strip() or None
            tok  = (r.get("token_list") or "").strip()

            # Strictly seed plasmid→fusions for the base (if tokens present)
            if tok:
                cx.execute(text("SELECT public.ensure_plasmid_fusions_from_list_strict(:code,:list)"),
                           {"code": base, "list": tok})
                seeded_tokens.append({"plasmid_code": base, "tokens": tok})

            # Upsert RNA row
            row = cx.execute(
                text("""
                  INSERT INTO public.rnas (rna_code, rna_name, base_plasmid_code, genetic_element, notes, created_by)
                  VALUES (:c,:n,:bp,NULL,:no,:by)
                  ON CONFLICT (rna_code) DO UPDATE
                    SET rna_name = COALESCE(EXCLUDED.rna_name, public.rnas.rna_name),
                        base_plasmid_code = EXCLUDED.base_plasmid_code,
                        notes = COALESCE(EXCLUDED.notes, public.rnas.notes)
                  RETURNING rna_code = :c AS is_update
                """),
                {"c": rc, "n": rn, "bp": base, "no": nt, "by": creator}
            ).mappings().first()
            if row and row.get("is_update"):
                updated.append(rc)
            else:
                inserted.append(rc)

    st.success(f"Uploaded RNAs • inserted: {len(inserted)} • updated: {len(updated)}")

    with _eng().begin() as cx:
        v = pd.read_sql(text("SELECT * FROM public.v_rnas WHERE rna_code = ANY(:codes) ORDER BY rna_code"),
                        cx, params={"codes": [*inserted, *updated]})
    if not v.empty:
        st.subheader("Verification (v_rnas)")
        st.dataframe(v, width="stretch", hide_index=True)
        st.download_button(
            "⬇︎ Download verification CSV",
            data=v.to_csv(index=False).encode("utf-8"),
            file_name="rnas_verification.csv",
            type="secondary"
        )
    if seeded_tokens:
        st.subheader("Plasmid fusion tokens processed")
        st.dataframe(pd.DataFrame(seeded_tokens), width="stretch", hide_index=True)