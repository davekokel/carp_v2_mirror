# carp_app/ui/pages/012_📤_upload_csv_tags.py
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
from carp_app.lib.time import utc_now

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Upload Tags", page_icon="📤", layout="wide")
st.title("📤 Upload Tags")
st.caption(
    "CSV/XLSX columns accepted: **nickname (tag name)**, **localization**, **note**, **citation_link**. "
    "Generates `tag_code` slug from `nickname` and upserts into "
    "`public.tags(tag_code, tag_name, localization, note, citation_link)`."
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

def _example_csv() -> bytes:
    df = pd.DataFrame([
        {"nickname":"2Xcox8A","localization":"mitochondria","note":"","citation_link":""},
        {"nickname":"sec61b","localization":"ER","note":"","citation_link":""},
        {"nickname":"LAMP1","localization":"lysosome","note":"","citation_link":""},
        {"nickname":"Lifeact","localization":"actin","note":"F-actin probe","citation_link":""},
    ])
    return df.to_csv(index=False).encode("utf-8")

st.download_button("⬇︎ Example tags.csv", data=_example_csv(),
                   file_name="tags_example.csv", mime="text/csv", use_container_width=True)

uploaded = st.file_uploader("Upload tags file (.csv or .xlsx)", type=["csv","xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin.")
    st.stop()

# Read file
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

# Map your headers + common aliases
aliases = {
    "nickname":       ["nickname","tag_name","tag","name","tag_nickname"],
    "localization":   ["localization","localisation","location","organelle"],
    "note":           ["note","notes","description","desc"],
    "citation_link":  ["citation_link","citation","link","url","reference"],
}
def pick(col: str) -> Optional[str]:
    for c in aliases[col]:
        if c in df.columns:
            return c
    return None

col_name = pick("nickname")
col_loc  = pick("localization")
col_note = pick("note")
col_link = pick("citation_link")

if not col_name:
    st.error("Missing required column: `nickname` (aka tag name).")
    st.stop()

out = pd.DataFrame({
    "tag_name": df[col_name].astype(str).map(lambda v: v.strip() if v and str(v).strip().lower() not in {"","none","nan"} else None),
    "localization": df[col_loc] if col_loc else "",
    "note":         df[col_note] if col_note else "",
    "citation_link":df[col_link] if col_link else "",
})
out["tag_code"] = out["tag_name"].map(_slug)

# QA checks
bad_rows = out[out["tag_name"].isna()].copy()
dup_mask = out["tag_code"].notna() & out["tag_code"].duplicated(keep=False)
dup_rows = out.loc[dup_mask].copy().sort_values(["tag_code","tag_name"])

st.subheader("Preview")
st.dataframe(out[["tag_name","localization","note","citation_link","tag_code"]].head(30),
             use_container_width=True, hide_index=True)
st.caption(f"{len(out)} rows")

qa_msgs: List[str] = []
if not bad_rows.empty:
    qa_msgs.append(f"{len(bad_rows)} row(s) missing `nickname` (tag name).")
if dup_mask.any():
    qa_msgs.append(f"{int(dup_mask.sum())} row(s) produce duplicate `tag_code` slugs in this file.")

if qa_msgs:
    st.warning("QA issues found:")
    for m in qa_msgs:
        st.markdown(f"- {m}")
    if not bad_rows.empty:
        st.markdown("**Rows missing `nickname` (tag name):**")
        st.dataframe(bad_rows.reset_index(drop=True), use_container_width=True, height=240)
    if not dup_rows.empty:
        st.markdown("**Rows with duplicate `tag_code` slugs:**")
        st.dataframe(dup_rows.reset_index(drop=True), use_container_width=True, height=240)
    flagged = pd.concat([bad_rows, dup_rows], ignore_index=True).drop_duplicates()
    st.download_button("⬇︎ Download flagged rows (CSV)",
                       data=flagged.to_csv(index=False).encode("utf-8"),
                       file_name="tags_qafail.csv",
                       mime="text/csv",
                       use_container_width=True)
    st.stop()

# Build param rows
rows: List[Dict[str, Any]] = []
for r in out.itertuples(index=False):
    if not r.tag_name or not r.tag_code:
        continue
    rows.append({
        "code":  r.tag_code,
        "name":  r.tag_name,
        "loc":   (r.localization if isinstance(r.localization, str) and r.localization.strip() else None),
        "note":  (r.note if isinstance(r.note, str) and r.note.strip() else None),
        "link":  (r.citation_link if isinstance(r.citation_link, str) and r.citation_link.strip() else None),
    })

if not rows:
    st.info("Nothing to insert.")
    st.stop()

if not st.button("Process upload", type="primary", use_container_width=True):
    st.stop()

# Upsert
created = 0
updated = 0
stmt = text("""
    INSERT INTO public.tags (tag_code, tag_name, localization, note, citation_link)
    VALUES (:code, :name, :loc, :note, :link)
    ON CONFLICT (tag_code) DO UPDATE
    SET  tag_name      = EXCLUDED.tag_name,
         localization  = COALESCE(EXCLUDED.localization,  public.tags.localization),
         note          = COALESCE(EXCLUDED.note,          public.tags.note),
         citation_link = COALESCE(EXCLUDED.citation_link, public.tags.citation_link)
    RETURNING (xmax = 0) AS inserted
""")

with _eng().begin() as cx:
    for params in rows:
        m = cx.execute(stmt, params).mappings().first()
        if m and m.get("inserted"):
            created += 1
        else:
            updated += 1

st.success(f"Done. Tags created: {created}, updated: {updated}")
st.download_button(
    "⬇︎ Uploaded tags (CSV)",
    data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
    file_name=f"tags_uploaded_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime="text/csv",
    use_container_width=True,
)