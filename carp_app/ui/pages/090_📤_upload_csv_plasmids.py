# carp_app/ui/pages/090_📤_upload_csv_plasmids.py
from __future__ import annotations

import sys, pathlib, io, os, re, math
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from typing import Optional, List, Dict, Tuple
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit import column_config as cc
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine
from carp_app.lib.time import utc_now

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock():
        return None

# ── Auth ─────────────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# ── Page UX ───────────────────────────────────────────────────────────────────
PAGE_TITLE = "CARP — Upload Plasmids from CSV"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)
st.caption(
    "CSV/XLSX must include **plasmid_code**. Optional: nickname, resistance, supports_invitro_rna, notes. "
    "Markers: **fluor_or_fluor_fusion_name** supports tokens like `Fluor` or `Tag:Fluor` "
    "(also `Tag::Fluor`, `Tag/Fluor`, `Tag@Fluor`, `Tag+Fluor`) and multiple tokens with `|`. "
    "**STRICT**: all referenced Fluors (and Tags, if present) must exist; otherwise the upload stops."
)

# ── Engine ───────────────────────────────────────────────────────────────────
_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

# ── Helpers ──────────────────────────────────────────────────────────────────
def _parse_bool(x) -> Optional[bool]:
    if x is None: return None
    s = str(x).strip().lower()
    if s in ("true","t","yes","y","1"): return True
    if s in ("false","f","no","n","0"): return False
    return None

def _read_upload(uploaded) -> pd.DataFrame:
    fname = (uploaded.name or "").lower()
    raw = io.BytesIO(uploaded.getvalue())
    if fname.endswith(".xlsx"):
        xls = pd.ExcelFile(raw)
        sheet = st.selectbox("Worksheet", xls.sheet_names, index=0)
        tmp = pd.read_excel(xls, sheet_name=sheet, header=None, dtype=object)
        tmp = tmp.applymap(lambda v: None if (v is Ellipsis or (isinstance(v, float) and math.isnan(v))) else v)
        header_row = None
        for i in range(min(20, len(tmp))):
            vals = [str(x).strip() if x is not None else "" for x in tmp.iloc[i].tolist()]
            if sum(bool(v) for v in vals) >= max(2, int(len(vals)*0.5)) and not all(v.lower().startswith("unnamed") for v in vals if v):
                header_row = i; break
        if header_row is None:
            raise RuntimeError("Could not detect header row")
        cols = [str(c).strip().lower() for c in tmp.iloc[header_row].fillna("").tolist()]
        df = tmp.iloc[header_row+1:].copy()
        df.columns = cols
        df = df.loc[:, [c for c in df.columns if c and not str(c).lower().startswith("unnamed")]]
        df.reset_index(drop=True, inplace=True)
        try:
            df = df.applymap(lambda v: None if v is Ellipsis else v)
        except Exception:
            df = df.replace({Ellipsis: None})
        return df
    else:
        df = pd.read_csv(raw, dtype=object)
        try:
            df = df.applymap(lambda v: None if v is Ellipsis else v)
        except Exception:
            df = df.replace({Ellipsis: None})
        return df

# ── Upload ───────────────────────────────────────────────────────────────────
uploaded = st.file_uploader("Upload plasmids (.csv or .xlsx)", type=["csv","xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin."); st.stop()

creator = getattr(user, "email", None) or os.environ.get("USER") or ""
seed_batch_id = Path(getattr(uploaded, "name", "")).stem

try:
    df = _read_upload(uploaded)
except Exception as e:
    st.error(f"Failed to read file: {e}"); st.stop()

# Normalize headers & aliases
df.columns = [c.strip().lower() for c in df.columns]
ALIASES: Dict[str, List[str]] = {
    "plasmid_code": ["code","plasmid","plasmid_base_code"],
    "nickname": ["nickname","name","plasmid_name"],
    "resistance": ["resistance","antibiotic","abx"],
    "supports_invitro_rna": ["supports_invitro_rna","supports_mrna","mrna_ok"],
    "notes": ["notes","note","desc","description"],
    # Accept your new header name, normalize to 'fusion_name'
    "fusion_name": ["fluor_or_fluor_fusion_name","fusion_name","fusions","fluors","fluor_list"]
}
rename: Dict[str,str] = {}
for target, alts in ALIASES.items():
    if target in df.columns: continue
    for a in alts:
        if a in df.columns:
            rename[a] = target; break
if rename:
    df.rename(columns=rename, inplace=True)

# Required + typing
if "plasmid_code" not in df.columns:
    st.error("Missing required column: plasmid_code"); st.stop()

for col in ("plasmid_code","nickname","resistance","notes","fusion_name"):
    if col in df.columns: df[col] = df[col].fillna("").astype(str)
if "supports_invitro_rna" in df.columns:
    df["supports_invitro_rna"] = df["supports_invitro_rna"].map(_parse_bool)

st.subheader("Preview (first 50 rows)")
st.dataframe(df.head(50), width="stretch", hide_index=True)

# ── STRICT Preflight (mixed Tag:Fluor OR Fluor:Tag; uses alt_names) ──────────
# Load catalogs to resolve both orders and aliases case-insensitively
def _load_catalogs(cx) -> tuple[set, set]:
    # Fluors: accept code, name, and any aliases in alt_names (text[] or text)
    flu_set: set[str] = set()
    rows = pd.read_sql(
        text("""
            SELECT
              lower(fluor_code)                               AS code_lc,
              lower(COALESCE(fluor_name, ''))                 AS name_lc,
              lower(COALESCE(
                CASE
                  WHEN pg_typeof(alt_names)::text = 'text[]'
                    THEN array_to_string(alt_names, ';')
                  ELSE alt_names::text
                END, ''
              ))                                             AS aliases_lc
            FROM public.fluors
        """),
        cx
    )
    for _, r in rows.iterrows():
        if r["code_lc"]:
            flu_set.add(r["code_lc"])
        if r["name_lc"]:
            flu_set.add(r["name_lc"])
        a = (r["aliases_lc"] or "").strip()
        if a:
            for alias in re.split(r"[;,\|]", a):
                alias = alias.strip()
                if alias:
                    flu_set.add(alias.lower())

    # Tags: accept code or name (text); handle case-insensitively
    tag_set: set[str] = set()
    rows2 = pd.read_sql(
        text("""
            SELECT lower(tag_code) AS code_lc,
                   lower(COALESCE(tag_name, '')) AS name_lc
            FROM public.tags
        """),
        cx
    )
    for _, r in rows2.iterrows():
        if r["code_lc"]:
            tag_set.add(r["code_lc"])
        if r["name_lc"]:
            tag_set.add(r["name_lc"])

    return flu_set, tag_set

def _split_token(tok: str) -> List[str]:
    parts = re.split(r"[:/@+]", (tok or "").strip())
    return [p.strip() for p in parts if p.strip()]

def _classify_token(parts: List[str], flu_set: set, tag_set: set) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns (fluor, tag, error_kind) where error_kind in {None,'unresolved_fluor','unresolved_tag','ambiguous'}.
    Rules:
      - single part: must be FLUOR
      - multi-part: decide sides by catalog membership (prefer left+right; collapse >2 by taking first and last)
    """
    if not parts:
        return None, None, None
    if len(parts) == 1:
        f = parts[0].lower()
        if f in flu_set:
            return parts[0], None, None
        return None, None, 'unresolved_fluor'
    left, right = parts[0].lower(), parts[-1].lower()
    left_is_flu  = left  in flu_set
    right_is_flu = right in flu_set
    left_is_tag  = left  in tag_set
    right_is_tag = right in tag_set

    # Exactly one side is flu → the other, if present, must be tag (or empty)
    if left_is_flu and (right_is_tag or right == ''):
        return parts[0], (parts[-1] if right_is_tag else None), None
    if right_is_flu and (left_is_tag or left == ''):
        return parts[-1], (parts[0] if left_is_tag else None), None

    # Ambiguity or missing
    if (left_is_flu and right_is_flu) or (left_is_tag and right_is_tag):
        return None, None, 'ambiguous'
    if not left_is_flu and not right_is_flu:
        return None, None, 'unresolved_fluor'
    # Fluor found but tag bad
    return (parts[0] if left_is_flu else parts[-1]), None, 'unresolved_tag'

# Parse tokens
tokens_raw: List[str] = []
if "fusion_name" in df.columns:
    for raw in df["fusion_name"].fillna(""):
        tokens_raw.extend([t.strip() for t in str(raw).split("|") if str(t).strip()])

unresolved_fluors, unresolved_tags, ambiguous = [], [], []

if tokens_raw:
    with _eng().begin() as cx:
        flu_set, tag_set = _load_catalogs(cx)

    for tok in tokens_raw:
        parts = _split_token(tok)
        fluor, tag, err = _classify_token(parts, flu_set, tag_set)
        if err == 'unresolved_fluor':
            unresolved_fluors.append(tok)
        elif err == 'unresolved_tag':
            unresolved_tags.append(tok)
        elif err == 'ambiguous':
            ambiguous.append(tok)

if unresolved_fluors or unresolved_tags or ambiguous:
    if unresolved_fluors:
        st.error(f"{len(unresolved_fluors)} unknown fluor token(s). Add to public.fluors (code/name/alt_names) or fix the CSV.")
        st.dataframe(pd.DataFrame({"unresolved_fluor_token": sorted(set(unresolved_fluors))}), hide_index=True, width="stretch")
    if unresolved_tags:
        st.error(f"{len(unresolved_tags)} unknown tag token(s). Add to public.tags or fix the CSV.")
        st.dataframe(pd.DataFrame({"unresolved_tag_token": sorted(set(unresolved_tags))}), hide_index=True, width="stretch")
    if ambiguous:
        st.error(f"{len(ambiguous)} ambiguous token(s) (both sides look like fluor or both like tag). Fix the CSV.")
        st.dataframe(pd.DataFrame({"ambiguous_token": sorted(set(ambiguous))}), hide_index=True, width="stretch")
    st.stop()

# ── Process (idempotent; forward-only) ───────────────────────────────────────
inserted, updated = [], []
fusion_tokens = []
ft_catalog = pd.DataFrame()

with _eng().begin() as cx:
    for _, r in df.iterrows():
        code = (r.get("plasmid_code") or "").strip()
        if not code:
            continue

        got = cx.execute(text("SELECT id FROM public.plasmids WHERE code=:c"), {"c": code}).mappings().first()

        fields = {
            "nickname": (r.get("nickname") or None),
            "resistance": (r.get("resistance") or None),
            "supports_invitro_rna": (r.get("supports_invitro_rna") if "supports_invitro_rna" in r else None),
            "notes": (r.get("notes") or None),
            "created_by": creator or None
        }

        if got:
            cx.execute(text("""
                UPDATE public.plasmids
                SET nickname = COALESCE(:nickname, nickname),
                    resistance = COALESCE(:resistance, resistance),
                    supports_invitro_rna = COALESCE(:supports_invitro_rna, supports_invitro_rna),
                    notes = COALESCE(:notes, notes)
                WHERE code = :code
            """), {**fields, "code": code})
            updated.append({"plasmid_code": code})
        else:
            cx.execute(text("""
                INSERT INTO public.plasmids (code, nickname, resistance, supports_invitro_rna, notes, created_by)
                VALUES (:code, :nickname, :resistance, :supports_invitro_rna, :notes, :created_by)
                ON CONFLICT (code) DO NOTHING
            """), {"code": code, **fields})
            inserted.append({"plasmid_code": code})

        flist = (r.get("fusion_name") or "").strip()
        if flist:
            cx.execute(
                text("SELECT public.ensure_plasmid_fusions_from_list_strict(:code,:list)"),
                {"code": code, "list": flist}
            )
            for tok in [t.strip() for t in flist.split("|") if str(t).strip()]:
                fusion_tokens.append({"plasmid_code": code, "token": tok})

        # Ensure TF master and derive FT markers for this base (forward-only)
        cx.execute(text("SELECT public.ensure_ft_markers_from_transgene(:ft)"), {"ft": code})

    st.success(f"Done. Processed {len(df)} row(s). Inserted {len(inserted)}, updated {len(updated)}.")

    plasmid_codes = sorted(set(df["plasmid_code"].tolist()))

    v_rich = pd.read_sql(
        text("""
          SELECT plasmid_code, plasmid_name, nickname, resistance, supports_invitro_rna,
                 fluor_names, tag_names, fusion_names
          FROM public.v_plasmids_rich
          WHERE plasmid_code = ANY(:codes)
          ORDER BY plasmid_code
        """),
        cx, params={"codes": plasmid_codes}
    )

    fu_detail = pd.read_sql(
        text("""
          SELECT p.code AS plasmid_code,
                 f.id   AS fusion_id,
                 COALESCE(fl.fluor_name,fl.fluor_code,'') AS fluor,
                 COALESCE(tg.tag_name,tg.tag_code,'')     AS tag
          FROM public.plasmids p
          JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id=p.id
          JOIN public.fusions f               ON f.id=jpf.fusion_id
          LEFT JOIN public.fluors fl          ON fl.id=f.fluor_id
          LEFT JOIN public.tags   tg          ON tg.id=f.tag_id
          WHERE p.code = ANY(:codes)
          ORDER BY p.code, f.id
        """),
        cx, params={"codes": plasmid_codes}
    )

    ft_catalog = pd.read_sql(
        text("""
          SELECT ft_code AS plasmid_base_code, fluor_code, COALESCE(tag_code,'') AS tag_code
          FROM public.ft_proteins
          WHERE ft_code = ANY(:codes)
          ORDER BY 1,2,3
        """),
        cx, params={"codes": plasmid_codes}
    )

# ── Summary ──────────────────────────────────────────────────────────────────
st.subheader("Summary")
c1, c2, c3 = st.columns(3)
c1.metric("Plasmids inserted", len(inserted))
c2.metric("Plasmids updated", len(updated))
c3.metric("Fusion tokens processed", len(fusion_tokens))

# ── Verification ─────────────────────────────────────────────────────────────
st.subheader("Verification")
if v_rich.empty:
    st.info("No plasmids found in v_plasmids_rich for this batch.")
else:
    st.caption("v_plasmids_rich")
    st.data_editor(
        v_rich,
        hide_index=True,
        width="stretch",
        column_config={
            "plasmid_code": cc.TextColumn("Plasmid code"),
            "plasmid_name": cc.TextColumn("Name"),
            "nickname":     cc.TextColumn("Nickname"),
            "resistance":   cc.TextColumn("Resistance"),
            "supports_invitro_rna": cc.CheckboxColumn("mRNA OK"),
            "fluor_names":  cc.TextColumn("Fluors"),
            "tag_names":    cc.TextColumn("Tags"),
            "fusion_names": cc.TextColumn("Fusions"),
        },
        key="plasmids_rich_editor",
    )

if not fu_detail.empty:
    st.caption("Resolved fusions → markers")
    st.data_editor(fu_detail, hide_index=True, width="stretch", key="fusions_editor")

if ft_catalog.empty:
    st.warning("No FT marker catalog entries exist yet for these plasmids. Ensure tokens resolve to known Fluors/Tags, then re-run.")
else:
    st.caption("FT marker catalog (ft_proteins)")
    st.data_editor(ft_catalog, hide_index=True, width="stretch", key="ft_catalog_editor")

# ── Downloads ────────────────────────────────────────────────────────────────
st.subheader("Downloads")
if inserted:
    st.download_button(
        "⬇︎ Inserted plasmids (CSV)",
        data=pd.DataFrame(inserted).to_csv(index=False).encode("utf-8"),
        file_name=f"plasmids_inserted_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        type="secondary"
    )
if updated:
    st.download_button(
        "⬇︎ Updated plasmids (CSV)",
        data=pd.DataFrame(updated).to_csv(index=False).encode("utf-8"),
        file_name=f"plasmids_updated_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        type="secondary"
    )
if fusion_tokens:
    st.download_button(
        "⬇︎ Fusion tokens processed (CSV)",
        data=pd.DataFrame(fusion_tokens).to_csv(index=False).encode("utf-8"),
        file_name=f"plasmid_fusion_tokens_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        type="secondary"
    )