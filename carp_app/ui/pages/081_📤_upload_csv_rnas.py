# carp_app/ui/pages/095_📤_upload_csv_rnas.py
from __future__ import annotations

import sys, pathlib, io, os, re
from typing import Optional, List, Dict
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── bootstrap ────────────────────────────────────────────────────────────────
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

# ── auth/page ────────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Upload RNAs from CSV", page_icon="📤", layout="wide")
st.title("CARP — Upload RNAs from CSV")
st.caption(
    "CSV/XLSX must include **rna_base_code**. Optional: **rna_name**, **notes**. "
    "Markers in **fluor_or_fluor_fusion_name** accept `Fluor`, `Tag:Fluor`, or `Fluor:Tag` (also `::`, `/`, `@`, `+`). "
    "If `rna_code` is blank, it becomes `RNA(<rna_base_code>)`. "
    "Markers are stored in **rna_proteins**. RNAs are independent from plasmids."
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

# ── normalize headers ────────────────────────────────────────────────────────
df.columns = [str(c).strip().lower() for c in df.columns]
ALIASES: Dict[str, List[str]] = {
    "rna_base_code": ["rna_base_code","base_plasmid_code","plasmid_code","base_code"],
    "rna_name":      ["rna_name","nickname","name","title"],
    "notes":         ["notes","note","desc","description"],
    "token_list":    ["fluor_or_fluor_fusion_name","fusion_name","fluors","fusions","fluor_list"],
    "rna_code":      ["rna_code","code","id"],
}
ren: Dict[str, str] = {}
for tgt, alts in ALIASES.items():
    if tgt in df.columns: continue
    for a in alts:
        if a in df.columns: ren[a] = tgt; break
if ren:
    df.rename(columns=ren, inplace=True)

# required
if "rna_base_code" not in df.columns:
    st.error("Missing required column: rna_base_code"); st.stop()

# clean
for c in ("rna_base_code","rna_name","notes","token_list","rna_code"):
    if c in df.columns:
        df[c] = df[c].fillna("").astype(str)

# rna_code default
if "rna_code" not in df.columns:
    df["rna_code"] = ""
df["rna_code"] = df.apply(lambda r: (r["rna_code"].strip() or f"RNA({str(r['rna_base_code']).strip()})"), axis=1)

st.subheader("Preview (first 50)")
st.dataframe(df[["rna_base_code","rna_code","rna_name","notes","token_list"]].head(50), width="stretch", hide_index=True)

# Optional soft warning if base isn’t in plasmids (no blocking)
bases = sorted(set(x.strip() for x in df["rna_base_code"].tolist() if str(x).strip()))
missing_plasmids: List[str] = []
if bases:
    with _eng().begin() as cx:
        present = pd.read_sql(text("SELECT code FROM public.plasmids WHERE code = ANY(:codes)"),
                              cx, params={"codes": bases})
    had = set(present["code"].tolist()) if not present.empty else set()
    missing_plasmids = [b for b in bases if b not in had]
if missing_plasmids:
    st.warning("These rna_base_code values are not present in `plasmids` (FYI only): " + ", ".join(missing_plasmids))

# ── STRICT token preflight for markers ───────────────────────────────────────
def _split_token(tok: str) -> List[str]:
    return [p.strip() for p in re.split(r"[:/@+]", (tok or "").strip()) if p.strip()]

def _load_catalogs(cx) -> tuple[set, set]:
    flu_set: set[str] = set()
    rows = pd.read_sql(
        text("""
          SELECT
            lower(fluor_code) AS c,
            lower(COALESCE(fluor_name,'')) AS n,
            lower(COALESCE(
              CASE WHEN pg_typeof(alt_names)::text = 'text[]'
                   THEN array_to_string(alt_names,';')
                   ELSE alt_names::text END, '')) AS a
          FROM public.fluors
        """), cx)
    for _, r in rows.iterrows():
        if r["c"]: flu_set.add(r["c"])
        if r["n"]: flu_set.add(r["n"])
        a = (r["a"] or "").strip()
        if a:
            for alias in re.split(r"[;,\|]", a):
                alias = alias.strip().lower()
                if alias: flu_set.add(alias)

    tag_set: set[str] = set()
    rows2 = pd.read_sql(text("SELECT lower(tag_code) AS c, lower(COALESCE(tag_name,'')) AS n FROM public.tags"), cx)
    for _, r in rows2.iterrows():
        if r["c"]: tag_set.add(r["c"])
        if r["n"]: tag_set.add(r["n"])
    return flu_set, tag_set

def _classify(parts: List[str], flu_set: set, tag_set: set) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not parts: return None, None, None
    if len(parts) == 1:
        f = parts[0].lower()
        return (parts[0], None, None) if f in flu_set else (None, None, 'unresolved_fluor')
    l, r = parts[0].lower(), parts[-1].lower()
    Lf, Rf = l in flu_set, r in flu_set
    Lt, Rt = l in tag_set, r in tag_set
    if Lf and (Rt or r==''): return (parts[0], parts[-1] if Rt else None, None)
    if Rf and (Lt or l==''): return (parts[-1], parts[0] if Lt else None, None)
    if (Lf and Rf) or (Lt and Rt): return (None, None, 'ambiguous')
    if not Lf and not Rf: return (None, None, 'unresolved_fluor')
    return (parts[0] if Lf else parts[-1], None, 'unresolved_tag')

tokens_raw: List[str] = []
if "token_list" in df.columns:
    for raw in df["token_list"].fillna(""):
        tokens_raw.extend([t.strip() for t in str(raw).split("|") if str(t).strip()])

unres_flu, unres_tag, ambig = [], [], []
flu_set: set[str] = set(); tag_set: set[str] = set()
if tokens_raw:
    with _eng().begin() as cx:
        flu_set, tag_set = _load_catalogs(cx)
    for tok in tokens_raw:
        parts = _split_token(tok)
        fluor, tag, err = _classify(parts, flu_set, tag_set)
        if err == 'unresolved_fluor': unres_flu.append(tok)
        elif err == 'unresolved_tag': unres_tag.append(tok)
        elif err == 'ambiguous':      ambig.append(tok)

if unres_flu or unres_tag or ambig:
    if unres_flu:
        st.error(f"{len(unres_flu)} unknown fluor token(s). Add to public.fluors or fix the CSV.")
        st.dataframe(pd.DataFrame({"unresolved_fluor_token": sorted(set(unres_flu))}), hide_index=True, width="stretch")
    if unres_tag:
        st.error(f"{len(unres_tag)} unknown tag token(s). Add to public.tags or fix the CSV.")
        st.dataframe(pd.DataFrame({"unresolved_tag_token": sorted(set(unres_tag))}), hide_index=True, width="stretch")
    if ambig:
        st.error(f"{len(ambig)} ambiguous token(s). Fix the CSV.")
        st.dataframe(pd.DataFrame({"ambiguous_token": sorted(set(ambig))}), hide_index=True, width="stretch")
    st.stop()

# ── process (idempotent) ────────────────────────────────────────────────────
inserted, updated, seeded = [], [], []

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

            # Insert/update RNA; map rna_base_code -> DB column base_plasmid_code (no FK)
            row = cx.execute(
                text("""
                  INSERT INTO public.rnas (rna_code, rna_name, base_plasmid_code, genetic_element, notes, created_by)
                  VALUES (:c,:n,:bp,NULL,:no,:by)
                  ON CONFLICT (rna_code) DO UPDATE
                    SET rna_name          = COALESCE(EXCLUDED.rna_name,          public.rnas.rna_name),
                        base_plasmid_code = COALESCE(EXCLUDED.base_plasmid_code, public.rnas.base_plasmid_code),
                        notes             = COALESCE(EXCLUDED.notes,             public.rnas.notes)
                  RETURNING (xmax::text <> '0') AS was_update
                """),
                {"c": rc, "n": rn, "bp": base, "no": nt, "by": creator}
            ).mappings().first()
            (updated if row and row.get("was_update") else inserted).append(rc)

            # Seed RNA markers in rna_proteins
            if tok:
                for raw_tok in [t.strip() for t in tok.split("|") if t.strip()]:
                    parts = _split_token(raw_tok)
                    fluor, tag, _ = _classify(parts, flu_set, tag_set) if tokens_raw else (None, None, None)
                    if fluor:
                        cx.execute(
                            text("""
                              INSERT INTO public.rna_proteins (rna_code, fluor_code, tag_code)
                              VALUES (:c,:flu, NULLIF(:tag,''))
                              ON CONFLICT (rna_code, COALESCE(tag_code,'∅'), fluor_code) DO NOTHING
                            """),
                            {"c": rc, "flu": fluor.strip(), "tag": (tag or "").strip()}
                        )
                        seeded.append({"rna_code": rc, "token": raw_tok})

    st.success(f"Uploaded RNAs • inserted: {len(inserted)} • updated: {len(updated)}")

    with _eng().begin() as cx:
        v = pd.read_sql(
            text("""
              SELECT rna_code, rna_name, base_plasmid_code,
                     COALESCE(fluor_names,'') AS fluor_names,
                     COALESCE(tag_names,'')   AS tag_names,
                     COALESCE(notes,'')       AS notes,
                     created_at
              FROM public.v_rnas
              WHERE rna_code = ANY(:codes)
              ORDER BY rna_code
            """),
            cx, params={"codes": [*inserted, *updated]}
        )
    if not v.empty:
        st.subheader("Verification (v_rnas)")
        st.dataframe(v, width="stretch", hide_index=True)
        st.download_button(
            "⬇︎ Download verification CSV",
            data=v.to_csv(index=False).encode("utf-8"),
            file_name="rnas_verification.csv",
            type="secondary"
        )
    if seeded:
        st.subheader("RNA marker tokens processed")
        st.dataframe(pd.DataFrame(seeded), width="stretch", hide_index=True)