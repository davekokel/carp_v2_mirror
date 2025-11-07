# carp_app/ui/pages/008_📤_upload_csv_fluors.py
from __future__ import annotations

import io, re, pathlib, sys, math
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Upload Fluors", page_icon="📤", layout="wide")
st.title("📤 Upload Fluors")
st.caption(
    "CSV/XLSX columns: **fluor_name (or fluor_nickname), excitation_nm, emission_nm, alt_names, notes**. "
    "Excitation/emission are **optional**; blanks or 0 are stored as NULL. "
    "alt_names may be separated by ';' ',' '|' or '/'."
)

# ── Engine ───────────────────────────────────────────────────────────────────
_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

# ── Helpers ──────────────────────────────────────────────────────────────────
def _to_smallint_or_none(v):
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    s = str(v).strip().lower()
    if s in {"", "nan", "none", "null"}: return None
    try:
        iv = int(float(s))
    except Exception:
        return None
    return None if iv == 0 else iv  # treat 0 as NULL

def _slug(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return re.sub(r"[^a-z0-9]+","-", str(s).strip().lower()).strip("-") or None

def _is_blank(x: Any) -> bool:
    if x is None: return True
    if isinstance(x, float) and math.isnan(x): return True
    s = str(x).strip().lower()
    return s in {"", "nan", "none", "null"}

def _parse_nm(x: Any) -> Optional[int]:
    """Return int nm or None. Treat blanks/0/'0' as NULL; otherwise coerce to int."""
    if _is_blank(x): return None
    try:
        v = int(float(str(x).strip()))
        return None if v == 0 else v
    except Exception:
        return None

def _split_alts(x: Any) -> List[str]:
    if _is_blank(x): return []
    parts = [p.strip() for p in re.split(r"[;,|/]", str(x)) if p.strip()]
    # de-dup case-insensitively, keep original case of first occurrence
    seen, out = set(), []
    for p in parts:
        k = p.lower()
        if k in seen: continue
        seen.add(k); out.append(p)
    return out

def _example_csv() -> bytes:
    df = pd.DataFrame([
        {"fluor_name":"mStayGold","excitation_nm":506,"emission_nm":550,"alt_names":"mSG; tdmStayGold","notes":"example"},
        {"fluor_name":"mChilada","excitation_nm":587,"emission_nm":610,"alt_names":"","notes":""},
        {"fluor_name":"Halo","excitation_nm":"","emission_nm":"","alt_names":"HaloTag; HT7; HaloTag7","notes":"Self-labeling tag; fluoresces with JF dyes"},
    ])
    return df.to_csv(index=False).encode("utf-8")

st.download_button("⬇︎ Example fluors.csv", data=_example_csv(),
                   file_name="fluors_example.csv", mime="text/csv", use_container_width=True)

# ── Upload file ──────────────────────────────────────────────────────────────
uploaded = st.file_uploader("Upload fluors file (.csv or .xlsx)", type=["csv","xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin."); st.stop()

try:
    raw = io.BytesIO(uploaded.getbuffer())
    if uploaded.name.lower().endswith(".xlsx"):
        df = pd.read_excel(raw, sheet_name=0, dtype=object)
    else:
        try:
            df = pd.read_csv(raw, dtype=object, encoding="utf-8")
        except UnicodeDecodeError:
            raw.seek(0)
            df = pd.read_csv(raw, dtype=object, encoding="latin1")
except Exception as e:
    st.error(f"Failed to read file: {e}"); st.stop()

df = df.copy()
df.columns = [str(c).strip().lower() for c in df.columns]

# Map incoming headers -> canonical
aliases = {
    "fluor_name":    ["fluor_name","fluor_nickname","fluor","name","nickname"],
    "excitation_nm": ["excitation_nm","ex_nm","exc","excitation"],
    "emission_nm":   ["emission_nm","em_nm","emi","emission"],
    "alt_names":     ["alt_names","aliases","aka","alts"],
    "notes":         ["notes","note","description","desc"],
}
def pick(col: str) -> Optional[str]:
    for c in aliases[col]:
        if c in df.columns:
            return c
    return None

col_nm = pick("fluor_name")
col_ex = pick("excitation_nm")
col_em = pick("emission_nm")
col_al = pick("alt_names")
col_nt = pick("notes")

if not col_nm:
    st.error("Missing required column: `fluor_name` (or `fluor_nickname`)."); st.stop()

# Build normalized frame
out = pd.DataFrame({
    "fluor_name": df[col_nm].map(lambda v: None if _is_blank(v) else str(v).strip()),
    "excitation_nm": df[col_ex] if col_ex else None,
    "emission_nm":   df[col_em] if col_em else None,
    "alt_names":     df[col_al] if col_al else "",
    "notes":         df[col_nt] if col_nt else "",
})

out["excitation_nm"] = out["excitation_nm"].map(_to_smallint_or_none)
out["emission_nm"]   = out["emission_nm"].map(_to_smallint_or_none)
out = out.astype({"excitation_nm": "object", "emission_nm": "object"})
out["fluor_code"]    = out["fluor_name"].map(_slug)

# Soft QA only (never blocking): count unusual nm values if any
soft_warn = []
unusual = out[
    (~out["excitation_nm"].isna() & ~out["excitation_nm"].between(250, 900)) |
    (~out["emission_nm"].isna()   & ~out["emission_nm"].between(250, 900))
]
if not unusual.empty:
    soft_warn.append(f"{len(unusual)} row(s) have wavelengths outside 250–900 nm (accepted).")

# Preview
st.subheader("Preview")
st.dataframe(out[["fluor_name","excitation_nm","emission_nm","alt_names","notes","fluor_code"]].head(30),
             use_container_width=True, hide_index=True)
st.caption(f"{len(out)} rows")
if soft_warn:
    for w in soft_warn:
        st.info(w)

# Build rows for upsert
rows = []
for r in out.itertuples(index=False):
    if not r.fluor_name or not r.fluor_code:
        continue
    ex = None if pd.isna(r.excitation_nm) else int(r.excitation_nm)
    em = None if pd.isna(r.emission_nm)   else int(r.emission_nm)
    rows.append({
        "code":  r.fluor_code,
        "name":  r.fluor_name,
        "ex":    ex,                          # guaranteed None or int
        "em":    em,                          # guaranteed None or int
        "alts":  _split_alts(r.alt_names) if isinstance(r.alt_names, str) else None,
        "notes": (r.notes if isinstance(r.notes, str) and r.notes.strip() else None),
    })

if not rows:
    st.info("Nothing to insert."); st.stop()

if not st.button("Process upload", type="primary", use_container_width=True):
    st.stop()

# Upsert (idempotent)
created = 0
updated = 0
stmt = text("""
    INSERT INTO public.fluors (fluor_code, fluor_name, excitation_nm, emission_nm, alt_names, notes)
    VALUES (:code, :name, :ex, :em, :alts, :notes)
    ON CONFLICT (fluor_code) DO UPDATE
    SET  fluor_name    = EXCLUDED.fluor_name,
         excitation_nm = COALESCE(EXCLUDED.excitation_nm, public.fluors.excitation_nm),
         emission_nm   = COALESCE(EXCLUDED.emission_nm,   public.fluors.emission_nm),
         alt_names     = COALESCE(EXCLUDED.alt_names,     public.fluors.alt_names),
         notes         = COALESCE(EXCLUDED.notes,         public.fluors.notes)
    RETURNING (xmax = 0) AS inserted
""")

with _eng().begin() as cx:
    for params in rows:
        m = cx.execute(stmt, params).mappings().first()
        if m and m.get("inserted"): created += 1
        else:                        updated += 1

st.success(f"Done. Fluors created: {created}, updated: {updated}")
st.download_button("⬇︎ Uploaded fluors (echo CSV)",
                   data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
                   file_name=f"fluors_uploaded.csv",
                   mime="text/csv",
                   use_container_width=True)