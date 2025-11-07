# carp_app/ui/pages/080_📤_upload_csv_fluors.py
from __future__ import annotations

import io, re, pathlib, sys
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

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Upload Fluors", page_icon="📤", layout="wide")
st.title("📤 Upload Fluors")
st.caption("CSV/XLSX columns: **fluor_name, excitation_nm, emission_nm, alt_names, notes**. "
           "QA checks: missing name, wavelength range (300–800 nm), duplicate `fluor_code` slugs. "
           "On success, upserts `public.fluors(fluor_code, fluor_name, excitation_nm, emission_nm, alt_names, notes)`.")

_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

def _slug(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return re.sub(r"[^a-z0-9]+", "-", str(s).strip().lower()).strip("-") or None

def _parse_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() in {"none","nan"}:
        return None
    try:
        return int(float(s))
    except Exception:
        return None

def _in_range_nm(v: Optional[int]) -> bool:
    return (v is None) or (300 <= v <= 800)

def _split_alts(x: Any) -> List[str]:
    if x is None:
        return []
    s = str(x).strip()
    if not s:
        return []
    return [a.strip() for a in re.split(r"[;,|]", s) if a.strip()]

def _example_csv() -> bytes:
    df = pd.DataFrame([
        {"fluor_name":"mStayGold","excitation_nm":506,"emission_nm":550,"alt_names":"mSG; tdmStayGold","notes":"example"},
        {"fluor_name":"GFP","excitation_nm":488,"emission_nm":510,"alt_names":"","notes":""},
        {"fluor_name":"Halo","excitation_nm":"","emission_nm":"","alt_names":"","notes":"protein tag"},
    ])
    return df.to_csv(index=False).encode("utf-8")

st.download_button("⬇︎ Example fluors.csv", data=_example_csv(),
                   file_name="fluors_example.csv", mime="text/csv", use_container_width=True)

uploaded = st.file_uploader("Upload fluors file (.csv or .xlsx)", type=["csv","xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin.")
    st.stop()

try:
    raw = io.BytesIO(uploaded.getbuffer())
    if uploaded.name.lower().endswith(".xlsx"):
        df = pd.read_excel(raw, sheet_name=0, dtype=object)
    else:
        df = pd.read_csv(raw, dtype=object)
except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

df = df.copy()
df.columns = [str(c).strip().lower() for c in df.columns]

aliases = {
    "fluor_name":    ["fluor_name","fluor","name"],
    "excitation_nm": ["excitation_nm","ex_nm","exc","excitation"],
    "emission_nm":   ["emission_nm","em_nm","emi","emission"],
    "alt_names":     ["alt_names","aliases","aka","alts"],
    "notes":         ["notes","note","description"],
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
    st.error("Missing required column: `fluor_name`")
    st.stop()

out = pd.DataFrame({
    "fluor_name": df[col_nm].astype(str).map(lambda v: v.strip() if v and str(v).strip().lower() not in {"","none","nan"} else None),
    "excitation_nm": df[col_ex] if col_ex else None,
    "emission_nm":   df[col_em] if col_em else None,
    "alt_names":     df[col_al] if col_al else "",
    "notes":         df[col_nt] if col_nt else "",
})

out["excitation_nm"] = out["excitation_nm"].map(_parse_int)
out["emission_nm"]   = out["emission_nm"].map(_parse_int)
out["fluor_code"]    = out["fluor_name"].map(_slug)

bad_rows = out[
    (out["fluor_name"].isna()) |
    (~out["excitation_nm"].map(_in_range_nm)) |
    (~out["emission_nm"].map(_in_range_nm))
].copy()

dup_mask  = out["fluor_code"].notna() & out["fluor_code"].duplicated(keep=False)
dup_rows  = out.loc[dup_mask].copy().sort_values(["fluor_code","fluor_name"])

qa_msgs: List[str] = []
if not bad_rows.empty:
    qa_msgs.append(f"{len(bad_rows)} row(s) have missing name or out-of-range wavelengths (300–800 nm).")
if dup_mask.any():
    qa_msgs.append(f"{int(dup_mask.sum())} row(s) produce duplicate `fluor_code` slugs in this file.")

st.subheader("Preview")
st.dataframe(out[["fluor_name","excitation_nm","emission_nm","alt_names","notes","fluor_code"]].head(30),
             use_container_width=True, hide_index=True)
st.caption(f"{len(out)} rows")

if qa_msgs:
    st.warning("QA issues found:")
    for m in qa_msgs:
        st.markdown(f"- {m}")
    if not bad_rows.empty:
        st.markdown("**Rows with missing name or out-of-range wavelengths (300–800 nm):**")
        st.dataframe(bad_rows[["fluor_name","excitation_nm","emission_nm","alt_names","notes","fluor_code"]]
                     .reset_index(drop=True), use_container_width=True, height=320)
    if not dup_rows.empty:
        st.markdown("**Rows with duplicate `fluor_code` slugs:**")
        st.dataframe(dup_rows[["fluor_name","excitation_nm","emission_nm","alt_names","notes","fluor_code"]]
                     .reset_index(drop=True), use_container_width=True, height=240)
    flagged = pd.concat([bad_rows, dup_rows], ignore_index=True).drop_duplicates()
    st.download_button("⬇︎ Download flagged rows (CSV)",
                       data=flagged.to_csv(index=False).encode("utf-8"),
                       file_name="fluors_qafail.csv",
                       mime="text/csv",
                       use_container_width=True)
    st.stop()

rows: List[Dict[str, Any]] = []
for r in out.itertuples(index=False):
    if not r.fluor_name or not r.fluor_code:
        continue
    rows.append({
        "code":  r.fluor_code,
        "name":  r.fluor_name,
        "ex":    r.excitation_nm,
        "em":    r.emission_nm,
        "alts":  [a for a in (re.split(r"[;,|]", r.alt_names) if isinstance(r.alt_names, str) else []) if a.strip()] or None,
        "notes": r.notes if isinstance(r.notes, str) and r.notes.strip() else None,
    })

if not rows:
    st.info("Nothing to insert.")
    st.stop()

if not st.button("Process upload", type="primary", use_container_width=True):
    st.stop()

created = 0
updated = 0
with _eng().begin() as cx:
    res = cx.execute(text("""
        INSERT INTO public.fluors (fluor_code, fluor_name, excitation_nm, emission_nm, alt_names, notes)
        VALUES (:code, :name, :ex, :em, :alts, :notes)
        ON CONFLICT (fluor_code) DO UPDATE
        SET  fluor_name    = EXCLUDED.fluor_name,
             excitation_nm = COALESCE(EXCLUDED.ex,    public.fluors.excitation_nm),
             emission_nm   = COALESCE(EXCLUDED.em,    public.fluors.emission_nm),
             alt_names     = COALESCE(EXCLUDED.alts,  public.fluors.alt_names),
             notes         = COALESCE(EXCLUDED.notes, public.fluors.notes)
        RETURNING (xmax = 0) AS inserted
    """), rows)
    for m in res.mappings():
        if m.get("inserted"):
            created += 1
        else:
            updated += 1

st.success(f"Done. Fluors created: {created}, updated: {updated}")
st.download_button("⬇︎ Uploaded fluors (echo CSV)",
                   data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
                   file_name=f"fluors_uploaded_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
                   mime="text/csv",
                   use_container_width=True)