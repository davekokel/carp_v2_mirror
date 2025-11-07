# carp_app/ui/pages/081_📤_upload_csv_dyes.py
from __future__ import annotations

import io, re, math, pathlib, sys
from typing import Any, Dict, List, Optional, Tuple

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
from carp_app.lib.time import utc_now

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Upload Dyes", page_icon="📤", layout="wide")
st.title("📤 Upload Dyes")
st.caption(
    "CSV/XLSX columns: dye_name (or dye/dye_nickname), excitation_nm, emission_nm, alt_names, notes, "
    "localization, binds_tag. At least one of localization or binds_tag is required. "
    "binds_tag must match an existing tag (code or name)."
)

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
    if s == "" or s.lower() in {"none", "nan"}:
        return None
    try:
        return int(float(s))
    except Exception:
        return None

def _in_range_nm(v: Optional[int]) -> bool:
    return (v is None) or (300 <= v <= 800)

def _is_blank(x: Any) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or str(x).strip() == "" or str(x).strip().lower() in {"none", "nan"}

def _split_list(x: Any) -> List[str]:
    if _is_blank(x):
        return []
    t = str(x).strip()
    parts = [p.strip() for p in re.split(r"[;,|/]", t) if p.strip()]
    seen = set()
    out: List[str] = []
    for p in parts:
        k = p.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out

def _example_csv() -> bytes:
    df = pd.DataFrame([
        {"dye_name": "LysoTracker Deep Red", "excitation_nm": 647, "emission_nm": 668, "alt_names": "", "notes": "acidotropic localization dye", "localization": "lysosome", "binds_tag": ""},
        {"dye_name": "JF549", "excitation_nm": 549, "emission_nm": 571, "alt_names": "Janelia Fluor 549; HaloTag ligand 549", "notes": "Halo ligand", "localization": "", "binds_tag": "Halo"},
    ])
    return df.to_csv(index=False).encode("utf-8")

st.download_button("⬇︎ Example dyes.csv", data=_example_csv(),
                   file_name="dyes_example.csv", mime="text/csv", use_container_width=True)

uploaded = st.file_uploader("Upload dyes file (.csv or .xlsx)", type=["csv", "xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin.")
    st.stop()

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
    st.error(f"Failed to read file: {e}")
    st.stop()

df = df.copy()
df.columns = [str(c).strip().lower() for c in df.columns]

aliases = {
    "dye_name":      ["dye_name", "dye", "name", "dye_nickname", "nickname"],
    "excitation_nm": ["excitation_nm", "ex_nm", "exc", "excitation"],
    "emission_nm":   ["emission_nm", "em_nm", "emi", "emission"],
    "alt_names":     ["alt_names", "aliases", "aka", "alts"],
    "notes":         ["notes", "note", "description", "desc"],
    "localization":  ["localization", "localisation", "location", "organelle"],
    "binds_tag":     ["binds_tag", "binds", "target_tag", "tag_target", "tag"],
}
def pick(key: str) -> Optional[str]:
    for c in aliases[key]:
        if c in df.columns:
            return c
    return None

col_nm  = pick("dye_name")
col_ex  = pick("excitation_nm")
col_em  = pick("emission_nm")
col_al  = pick("alt_names")
col_nt  = pick("notes")
col_loc = pick("localization")
col_bt  = pick("binds_tag")

if not col_nm:
    st.error("Missing required column: `dye_name` (or dye/dye_nickname).")
    st.stop()

out = pd.DataFrame({
    "dye_name":      df[col_nm].astype(str).map(lambda v: v.strip() if not _is_blank(v) else None),
    "excitation_nm": df[col_ex] if col_ex else None,
    "emission_nm":   df[col_em] if col_em else None,
    "alt_names":     df[col_al] if col_al else "",
    "notes":         df[col_nt] if col_nt else "",
    "localization":  df[col_loc] if col_loc else "",
    "binds_tag":     df[col_bt] if col_bt else "",
})

out["excitation_nm"] = out["excitation_nm"].map(_parse_int)
out["emission_nm"]   = out["emission_nm"].map(_parse_int)
out["dye_code"]      = out["dye_name"].map(_slug)

bad_rows = out[
    (out["dye_name"].isna()) |
    (~out["excitation_nm"].map(_in_range_nm)) |
    (~out["emission_nm"].map(_in_range_nm))
].copy()

dup_mask  = out["dye_code"].notna() & out["dye_code"].duplicated(keep=False)
dup_rows  = out.loc[dup_mask].copy().sort_values(["dye_code", "dye_name"])

needs_target = out[
    out["localization"].map(_is_blank) & out["binds_tag"].map(_is_blank)
].copy()

st.subheader("Preview")
st.dataframe(out[["dye_name", "excitation_nm", "emission_nm", "alt_names", "notes", "localization", "binds_tag", "dye_code"]].head(30),
             use_container_width=True, hide_index=True)
st.caption(f"{len(out)} rows")

qa_msgs: List[str] = []
if not bad_rows.empty:
    qa_msgs.append(f"{len(bad_rows)} row(s) have missing name or out-of-range wavelengths (300–800 nm).")
if dup_mask.any():
    qa_msgs.append(f"{int(dup_mask.sum())} row(s) produce duplicate `dye_code` slugs in this file.")
if not needs_target.empty:
    qa_msgs.append(f"{len(needs_target)} row(s) require either `localization` or `binds_tag`.")

def _fetch_tag_index(cx) -> Dict[str, Tuple[str, str]]:
    rows = cx.execute(text("""
        select id::text, lower(tag_code), coalesce(tag_name, tag_code) from public.tags
        union
        select id::text, lower(tag_name), coalesce(tag_name, tag_code) from public.tags where tag_name is not null
    """)).all()
    return {r[1]: (r[0], r[2]) for r in rows if r[1]}

unknown_bind_rows = pd.DataFrame()
with _eng().begin() as cx:
    tag_idx = _fetch_tag_index(cx)

bind_lists = out["binds_tag"].map(_split_list)
unknown_mask = bind_lists.map(lambda lst: any(s.strip().lower() not in tag_idx for s in lst))
if unknown_mask.any():
    unknown_bind_rows = out.loc[unknown_mask].copy()
    qa_msgs.append(f"{int(unknown_mask.sum())} row(s) reference unknown tag(s) in `binds_tag` (must match code or name).")

if qa_msgs:
    st.warning("QA issues found:")
    for m in qa_msgs:
        st.markdown(f"- {m}")
    if not bad_rows.empty:
        st.markdown("**Rows with missing name or out-of-range wavelengths:**")
        st.dataframe(bad_rows.reset_index(drop=True), use_container_width=True, height=240)
    if not dup_rows.empty:
        st.markdown("**Rows with duplicate `dye_code` slugs:**")
        st.dataframe(dup_rows.reset_index(drop=True), use_container_width=True, height=240)
    if not needs_target.empty:
        st.markdown("**Rows missing both `localization` and `binds_tag`:**")
        st.dataframe(needs_target.reset_index(drop=True), use_container_width=True, height=240)
    if not unknown_bind_rows.empty:
        st.markdown("**Rows with unknown `binds_tag` values:**")
        st.dataframe(unknown_bind_rows.reset_index(drop=True), use_container_width=True, height=240)
    st.download_button("⬇︎ Download QA failures (CSV)",
                       data=pd.concat([bad_rows, dup_rows, needs_target, unknown_bind_rows]).drop_duplicates().to_csv(index=False).encode("utf-8"),
                       file_name="dyes_qafail.csv", mime="text/csv", use_container_width=True)
    st.stop()

rows: List[Dict[str, Any]] = []
for r in out.itertuples(index=False):
    if not r.dye_name or not r.dye_code:
        continue
    rows.append({
        "code":  r.dye_code,
        "name":  r.dye_name,
        "ex":    r.excitation_nm,
        "em":    r.emission_nm,
        "alts":  (_split_list(r.alt_names) if not _is_blank(r.alt_names) else None),
        "notes": (r.notes if not _is_blank(r.notes) else None),
        "loc":   (r.localization if not _is_blank(r.localization) else None),
    })

if not rows:
    st.info("Nothing to insert.")
    st.stop()

if not st.button("Process upload", type="primary", use_container_width=True):
    st.stop()

created = 0
updated = 0
stmt = text("""
    INSERT INTO public.dyes (dye_code, dye_name, excitation_nm, emission_nm, alt_names, notes, localization)
    VALUES (:code, :name, :ex, :em, :alts, :notes, :loc)
    ON CONFLICT (dye_code) DO UPDATE
    SET  dye_name      = EXCLUDED.dye_name,
         excitation_nm = COALESCE(EXCLUDED.excitation_nm, public.dyes.excitation_nm),
         emission_nm   = COALESCE(EXCLUDED.emission_nm,   public.dyes.emission_nm),
         alt_names     = COALESCE(EXCLUDED.alt_names,     public.dyes.alt_names),
         notes         = COALESCE(EXCLUDED.notes,         public.dyes.notes),
         localization  = COALESCE(EXCLUDED.localization,  public.dyes.localization)
    RETURNING (xmax = 0) AS inserted
""")

with _eng().begin() as cx:
    for params in rows:
        m = cx.execute(stmt, params).mappings().first()
        if m and m.get("inserted"):
            created += 1
        else:
            updated += 1

st.success(f"Done. Dyes created: {created}, updated: {updated}")
st.download_button(
    "⬇︎ Uploaded dyes (CSV)",
    data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
    file_name=f"dyes_uploaded_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime="text/csv",
    use_container_width=True,
)