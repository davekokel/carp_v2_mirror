# carp_app/ui/pages/011_📤_upload_csv_fusions.py
from __future__ import annotations

import sys, pathlib, io, re
from typing import Optional, List, Dict

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine
from carp_app.lib.time import utc_now

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Upload Fusions", page_icon="📤", layout="wide")
st.title("📤 Upload Fusions")
st.caption("CSV/XLSX columns: **fusion_nickname, fluor, tag, tag_location**. "
           "Upserts catalogs (fluors/tags), builds a prefix-free *fusion_code* from tag_location, "
           "and inserts fusions by IDs.")

# ── DB engine ────────────────────────────────────────────────────────────────
_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

# ── Helpers ──────────────────────────────────────────────────────────────────
def _slug(s: Optional[str]) -> Optional[str]:
    if not s: return None
    z = re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")
    return z or None

def _norm(s: Optional[str]) -> Optional[str]:
    if s is None: return None
    s = str(s).strip()
    return s if s else None

def _norm_loc(s: Optional[str]) -> str:
    if not s: return ""
    z = s.strip().lower()
    z = z.replace("n-term","n_terminal").replace("n terminal","n_terminal").replace("n-terminal","n_terminal")
    z = z.replace("c-term","c_terminal").replace("c terminal","c_terminal").replace("c-terminal","c_terminal")
    if z in {"n","n_terminus"}: z = "n_terminal"
    if z in {"c","c_terminus"}: z = "c_terminal"
    return z if z in {"n_terminal","c_terminal"} else ""

def _fusion_code(fluor: Optional[str], tag: Optional[str], loc: str) -> str:
    f = _slug(fluor) or ""
    t = _slug(tag) or ""
    if t:
        parts = [t, f] if loc == "n_terminal" else ([f, t] if loc == "c_terminal" else [f, t])
    else:
        parts = [f]
    return "-".join([p for p in parts if p])

def _pretty_name(nick: Optional[str], fluor: Optional[str], tag: Optional[str], loc: str) -> str:
    if nick: return nick
    if fluor and tag:
        # use fluor::tag as a compact human label regardless of position
        return f"{fluor}::{tag}"
    return fluor or ""

def _example_csv() -> bytes:
    df = pd.DataFrame([
        {"fusion_nickname":"2Xcox8A::mStayGold","fluor":"mStayGold","tag":"2Xcox8A","tag_location":"n_terminal"},
        {"fusion_nickname":"mChilada::sec61b","fluor":"mChilada","tag":"sec61b","tag_location":"c_terminal"},
        {"fusion_nickname":"GFP only","fluor":"GFP","tag":"","tag_location":""},
    ])
    return df.to_csv(index=False).encode("utf-8")

# ── UI ───────────────────────────────────────────────────────────────────────
st.download_button("⬇︎ Example fusions.csv", data=_example_csv(),
                   file_name="fusions_example.csv", mime="text/csv", type="secondary")

uploaded = st.file_uploader("Upload fusions file (.csv or .xlsx)", type=["csv","xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin."); st.stop()

# Read file
try:
    raw = io.BytesIO(uploaded.getbuffer())
    if uploaded.name.lower().endswith(".xlsx"):
        df = pd.read_excel(raw, sheet_name=0, dtype=object)
    else:
        df = pd.read_csv(raw, dtype=object)
except Exception as e:
    st.error(f"Failed to read file: {e}"); st.stop()

# Normalize headers
df.columns = [str(c).strip().lower() for c in df.columns]
aliases = {
    "fusion_nickname": ["fusion_nickname","fusion","nickname","fusion name"],
    "fluor":           ["fluor","fluor_name","fluor name"],
    "tag":             ["tag","tag_name","tag name"],
    "tag_location":    ["tag_location","tag location","location","tagloc","position"],
}
def pick(key: str) -> Optional[str]:
    for c in aliases[key]:
        if c in df.columns: return c
    return None

col_fn  = pick("fusion_nickname")
col_fl  = pick("fluor")
col_tag = pick("tag")
col_loc = pick("tag_location")

missing = [n for n,c in [("fusion_nickname",col_fn),("fluor",col_fl)] if c is None]
if missing:
    st.error(f"Missing required columns: {', '.join(missing)}"); st.stop()

# Clean values
for c in [col_fn, col_fl, col_tag, col_loc]:
    if c in df.columns:
        df[c] = df[c].astype(str).map(lambda v: None if v.strip() in {"", "None", "nan", "NaN"} else v.strip())

# Preview
st.subheader("Preview")
st.dataframe(df.head(30), use_container_width=True, hide_index=True)
st.caption(f"{len(df)} rows")

# Build intended rows
rows: List[Dict[str, Optional[str]]] = []
for r in df.itertuples(index=False):
    nick  = _norm(getattr(r, col_fn))
    fluor = _norm(getattr(r, col_fl))
    tag   = _norm(getattr(r, col_tag)) if col_tag else None
    loc   = _norm_loc(getattr(r, col_loc)) if col_loc else ""
    if not fluor:
        continue
    code  = _fusion_code(fluor, tag, loc)
    if not code:
        continue
    name  = _pretty_name(nick, fluor, tag, loc)
    rows.append({"fusion_code": code, "fusion_name": name, "fluor_name": fluor, "tag_name": tag})

if not rows:
    st.warning("No valid fusion rows found (need at least 'fluor')."); st.stop()

st.subheader("Fusions to upsert")
st.dataframe(pd.DataFrame(rows).head(30), use_container_width=True, hide_index=True)

if not st.button("Process upload", type="primary", use_container_width=True):
    st.stop()

# Process (ID-first)
created = 0
updated = 0
issues  = []

with _eng().begin() as cx:
    # Upsert fluors
    fluors: Dict[str,str] = {}
    for nm in sorted({r["fluor_name"] for r in rows if r["fluor_name"]}):
        slug = _slug(nm)
        if not slug:
            issues.append(f"Fluor produced empty slug: {nm!r}")
            continue
        cx.execute(text("""
          INSERT INTO public.fluors (fluor_code, fluor_name)
          VALUES (:code, :name)
          ON CONFLICT (fluor_code) DO UPDATE SET fluor_name = EXCLUDED.fluor_name
        """), {"code": slug, "name": nm})
        fid = cx.execute(text("SELECT id FROM public.fluors WHERE fluor_code=:c"), {"c": slug}).scalar()
        if fid is None:
            issues.append(f"Fluor unresolved after upsert: {nm}")
            continue
        fluors[nm] = fid

    # Upsert tags (optional)
    tags: Dict[str,str] = {}
    for nm in sorted({r["tag_name"] for r in rows if r["tag_name"]}):
        slug = _slug(nm)
        if not slug:
            issues.append(f"Tag produced empty slug: {nm!r}")
            continue
        cx.execute(text("""
          INSERT INTO public.tags (tag_code, tag_name)
          VALUES (:code, :name)
          ON CONFLICT (tag_code) DO UPDATE SET tag_name = EXCLUDED.tag_name
        """), {"code": slug, "name": nm})
        tid = cx.execute(text("SELECT id FROM public.tags WHERE tag_code=:c"), {"c": slug}).scalar()
        if tid is None:
            issues.append(f"Tag unresolved after upsert: {nm}")
            continue
        tags[nm] = tid

    # Upsert fusions by IDs
    for r in rows:
        fid = fluors.get(r["fluor_name"])
        tid = tags.get(r["tag_name"]) if r["tag_name"] else None
        if fid is None:
            issues.append(f"Missing fluor_id for row: {r}")
            continue
        res = cx.execute(text("""
          INSERT INTO public.fusions (fusion_code, fusion_name, fluor_id, tag_id)
          VALUES (:code, :name, :fid, :tid)
          ON CONFLICT (fusion_code) DO UPDATE
          SET fusion_name = EXCLUDED.fusion_name,
              fluor_id    = EXCLUDED.fluor_id,
              tag_id      = EXCLUDED.tag_id
          RETURNING (xmax = 0) AS inserted
        """), {"code": r["fusion_code"], "name": r["fusion_name"], "fid": fid, "tid": tid}).mappings().first()
        if res and res.get("inserted"):
            created += 1
        else:
            updated += 1

st.success(f"Done. Fusions created: {created}, updated: {updated}.")
if issues:
    st.warning("Some items need attention:")
    st.code("\n".join(issues), language="text")

st.download_button(
    "⬇︎ Uploaded fusions (CSV)",
    data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
    file_name=f"fusions_uploaded_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime="text/csv",
    type="secondary",
    use_container_width=True,
)