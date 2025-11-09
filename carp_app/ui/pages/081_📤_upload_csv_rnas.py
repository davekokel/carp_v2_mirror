# carp_app/ui/pages/095_📤_upload_csv_rnas.py
from __future__ import annotations

import sys, pathlib, io, os, re, json
from typing import Optional, List, Dict, Tuple
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
st.title("CARP — Upload RNAs from CSV (v6)")
st.caption(
    "CSV/XLSX must include **rna_base_code**. Optional: **rna_name** (stored as nickname), **notes**. "
    "Markers in **fluor_or_fluor_fusion_name** accept `Fluor` or `Fluor::Tag` (also `:`, `/`, `@`, `+`). "
    "If `rna_code` is blank, it becomes `RNA(<rna_base_code>)`. "
    "Markers are linked via **join_rna_fusions**."
)

# ── engine ──────────────────────────────────────────────────────────────────
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
    "token_list":    ["fluor_or_fluor_fusion_name","fusion_name","fluors","fusions","fluor_list","marker_list","tokens"],
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
preview_cols = [c for c in ["rna_base_code","rna_code","rna_name","notes","token_list"] if c in df.columns]
st.dataframe(df[preview_cols].head(50), width="stretch", hide_index=True)

# ── token utilities ─────────────────────────────────────────────────────────
def _split_token(tok: str) -> List[str]:
    return [p.strip() for p in re.split(r"[:/@+]", (tok or "").strip()) if p.strip()]

def _load_catalogs(cx) -> Tuple[set, set]:
    flu_set: set[str] = set()
    rows = pd.read_sql(
        text("""
          SELECT
            lower(fluor_code)              AS c,
            lower(COALESCE(fluor_name,'')) AS n,
            lower(COALESCE(alt_names,''))  AS a     -- alt_names is text in v6
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
    rows2 = pd.read_sql(
        text("SELECT lower(tag_code) AS c, lower(COALESCE(tag_name,'')) AS n FROM public.tags"), cx
    )
    for _, r in rows2.iterrows():
        if r["c"]: tag_set.add(r["c"])
        if r["n"]: tag_set.add(r["n"])
    return flu_set, tag_set

def _classify(parts: List[str], flu_set: set, tag_set: set) -> Tuple[Optional[str], Optional[str], Optional[str]]:
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

# ── STRICT token preflight for markers ───────────────────────────────────────
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
    col1, col2, col3 = st.columns(3)
    if unres_flu:
        with col1:
            st.error(f"{len(set(unres_flu))} unknown fluor token(s). Add to public.fluors or fix the CSV.")
            st.dataframe(pd.DataFrame({"unresolved_fluor_token": sorted(set(unres_flu))}), hide_index=True, width="stretch")
    if unres_tag:
        with col2:
            st.error(f"{len(set(unres_tag))} unknown tag token(s). Add to public.tags or fix the CSV.")
            st.dataframe(pd.DataFrame({"unresolved_tag_token": sorted(set(unres_tag))}), hide_index=True, width="stretch")
    if ambig:
        with col3:
            st.error(f"{len(set(ambig))} ambiguous token(s). Fix the CSV.")
            st.dataframe(pd.DataFrame({"ambiguous_token": sorted(set(ambig))}), hide_index=True, width="stretch")
    st.stop()

# ── process (idempotent) ────────────────────────────────────────────────────
inserted, updated, linked = [], [], []

if st.button("Process RNA upload", type="primary", use_container_width=True):
    with _eng().begin() as cx:
        for _, r in df.iterrows():
            base = (r.get("rna_base_code") or "").strip()
            rc   = (r.get("rna_code")      or "").strip()
            rn   = (r.get("rna_name")      or "").strip() or None   # → nickname
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
                    fluor, tag, _ = _classify(parts, flu_set, tag_set) if tokens_raw else (None, None, None)
                    combo = raw_tok if re.search(r"[:/@+]", raw_tok) else (fluor or "")
                    if not combo: continue
                    fusion_id_row = cx.execute(text("SELECT public.resolve_fusion_id(:combo) AS id"), {"combo": combo}).mappings().first()
                    if fusion_id_row and fusion_id_row["id"]:
                        cx.execute(
                            text("""
                              INSERT INTO public.join_rna_fusions (rna_id, fusion_id)
                              VALUES (:rid, :fid)
                              ON CONFLICT DO NOTHING
                            """),
                            {"rid": rna_id, "fid": fusion_id_row["id"]}
                        )
                        linked.append({"rna_code": rc, "token": raw_tok})

    st.success(f"Uploaded RNAs • inserted: {len(inserted)} • updated: {len(updated)} • linked: {len(linked)}")

    with _eng().begin() as cx:
        v = pd.read_sql(
            text("""
              SELECT
                rna_code,
                COALESCE(nickname,'') AS nickname,
                COALESCE(notes,'')    AS notes,
                COALESCE(fluors,'')   AS fluors,
                COALESCE(tags,'')     AS tags,
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