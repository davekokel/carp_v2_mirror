# carp_app/ui/pages/008_📤_upload_csv_fish.py
from __future__ import annotations

import sys, pathlib, io, os, re, math
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from typing import Optional, List, Dict
from datetime import date, timedelta
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
    def require_app_unlock(): ...

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

PAGE_TITLE = "CARP — New Fish from CSV (fluorescent treatments)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)
st.caption("CSV/XLSX must include **birthday**. Humans set **nickname**. The database manages treatments and markers.")

_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

def _col_exists(cx, schema: str, table: str, column: str) -> bool:
    q = text("""
      select exists (
        select 1 from information_schema.columns
        where table_schema=:s and table_name=:t and column_name=:c
      )
    """)
    return bool(cx.execute(q, {"s": schema, "t": table, "c": column}).scalar())

def _norm_str(v):
    if v is None:
        return ""
    s = str(v).strip().lower()
    return " ".join(s.split())

def _identity_key(r: pd.Series) -> str:
    parts = [
        str(r.get("birthday") or "").strip(),
        _norm_str(r.get("genetic_background")),
        _norm_str(r.get("line_building_stage")),
        _norm_str(r.get("ft_code") or r.get("mix_code") or r.get("transgene_base_code")),
        _norm_str(r.get("allele_nickname")),
    ]
    return " | ".join(parts)

_NUM_NICK_RE = re.compile(r"^\d+(?:\.0+)?$")
def _canon_nickname(s: str) -> str:
    s = (s or "").strip()
    if _NUM_NICK_RE.match(s):
        return re.sub(r"\.0+$", "", s)
    return s

def _parse_birthday(x) -> Optional[date]:
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        y, m, d = map(int, s.split("-")); return date(y, m, d)
    if re.fullmatch(r"\d{8}", s):
        y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8]); return date(y, m, d)
    try:
        n = float(s)
        if not math.isnan(n): return date(1899,12,30) + timedelta(days=int(n))
    except Exception:
        ...
    try:
        from dateutil import parser
        return parser.parse(s).date()
    except Exception:
        return None

def _example_fish_csv_bytes() -> bytes:
    example = pd.DataFrame([{
        "nickname": "",
        "birthday": "2025-01-15",
        "genetic_background": "casper",
        "line_building_stage": "F0",
        "description": "",
        "ft_code": "injmix-0001",
        "ft_text": "example injection mix",
        "fluor_code": "mScarlet",
        "tag_code": "myc",
        "allele_nickname": "505",
        "zygosity": ""
    }])
    return example.to_csv(index=False).encode("utf-8")

st.download_button(
    "⬇︎ Example CSV (no 'name'; treatments + markers by columns)",
    data=_example_fish_csv_bytes(),
    file_name="fish_example.csv",
    mime="text/csv",
)

uploaded = st.file_uploader("Upload fish file (.csv or .xlsx)", type=["csv", "xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin."); st.stop()

default_batch = Path(getattr(uploaded, "name", "")).stem
seed_batch_id = st.text_input("Seed batch ID", value=default_batch)

creator_uuid = getattr(user, "id", None)
created_by = getattr(user, "email", None) or os.environ.get("USER") or ""

# Read file with simple header handling (CSV) and resilient header detect (XLSX)
try:
    fname = (uploaded.name or "").lower()
    raw = io.BytesIO(uploaded.getvalue())
    if fname.endswith(".xlsx"):
        xls = pd.ExcelFile(raw)
        sheet = st.selectbox("Worksheet", xls.sheet_names, index=0)
        tmp = pd.read_excel(xls, sheet_name=sheet, header=None, dtype=object)
        tmp = tmp.applymap(lambda v: v if not (isinstance(v, float) and math.isnan(v)) else None)
        header_row = None
        for i in range(min(20, len(tmp))):
            vals = [str(x).strip() if x is not None else "" for x in tmp.iloc[i].tolist()]
            if sum(bool(v) for v in vals) >= max(2, int(len(vals)*0.5)) and not all(v.lower().startswith("unnamed") for v in vals if v):
                header_row = i; break
        if header_row is None:
            st.error("Could not detect header row. Ensure first non-empty row contains column names."); st.stop()
        cols = [str(c).strip().lower() for c in tmp.iloc[header_row].fillna("").tolist()]
        df = tmp.iloc[header_row+1:].copy()
        df.columns = cols
        df = df.loc[:, [c for c in df.columns if c and not str(c).lower().startswith("unnamed")]]
        df.reset_index(drop=True, inplace=True)
    else:
        df = pd.read_csv(raw, dtype=object)
except Exception as e:
    st.error(f"Failed to read file: {e}"); st.stop()

# Normalize by name (order-agnostic) + aliases
df.columns = [c.strip().lower() for c in df.columns]
ALIASES = {
    "birthday": ["dob","date_birth","date of birth"],
    "ft_code": ["ft_code","mix_code","transgene_base_code","base_code","tg_base_code","transgene_base","tg_base"],
    "ft_text": ["ft_text","mix_text","treatment_text","notes","description"],
    "allele_nickname": ["allele_nickname","allele_nick","allele_name","allele"],
    "zygosity": ["zygosity","zyg","allele_zygosity"],
    "fluor_code": ["fluor_code","fluor","fluorname"],
    "tag_code": ["tag_code","tag","tagname"],
    "dye_code": ["dye_code","dye","dyename"],
    "nickname": ["nickname","nick"],
    "genetic_background": ["genetic_background","background","bg","strain"],
    "line_building_stage": ["line_building_stage","stage","lb_stage","line_stage"],
}
rename: Dict[str,str] = {}
for target, alts in ALIASES.items():
    if target in df.columns: continue
    for a in alts:
        if a in df.columns:
            rename[a] = target; break
if rename:
    df.rename(columns=rename, inplace=True)

# Required headers
if "birthday" not in df.columns:
    st.error("Missing required column: birthday"); st.stop()

# Clean and types
if "fish_code" in df.columns:
    df.drop(columns=["fish_code"], inplace=True)
for c in ("nickname","genetic_background","line_building_stage","ft_code","ft_text",
          "fluor_code","tag_code","dye_code","allele_nickname","zygosity"):
    if c in df.columns: df[c] = df[c].fillna("").astype(str)
df["birthday"] = df["birthday"].apply(_parse_birthday)
if df["birthday"].isna().any():
    st.error("One or more rows have an invalid birthday."); st.stop()

st.subheader("Preview (first 50 rows)")
st.dataframe(df.head(50), use_container_width=True, hide_index=True)

# Resolved column names for code/markers
col_ft = "ft_code" if "ft_code" in df.columns else None
col_flu = "fluor_code" if "fluor_code" in df.columns else None
col_tag = "tag_code"   if "tag_code"   in df.columns else None
col_dye = "dye_code"   if "dye_code"   in df.columns else None
col_nick= "allele_nickname" if "allele_nickname" in df.columns else None
col_zyg = "zygosity"        if "zygosity"        in df.columns else None

def _fetch_vfish_rollup(cx, fish_codes: List[str]) -> pd.DataFrame:
    if not fish_codes:
        return pd.DataFrame(columns=["fish_code","markers","fluors","tags","dyes"])
    q = text("""
      SELECT fish_code, markers, fluors, tags, dyes
      FROM public.v_fish_fluorescent_markers
      WHERE fish_code = ANY(:codes)
      ORDER BY fish_code
    """)
    return pd.read_sql(q, cx, params={"codes": list({c for c in fish_codes if c})})

inserted: List[Dict[str,str]] = []

if st.button("Process upload (create/update fish + fluorescent treatments)", type="primary"):
    linked, skipped = 0, 0

    fn_upsert_fish = text("""
      select * from public.upsert_fish_by_identity(
        :p_seed_batch_id,:p_identity_key,:p_dob,:p_name_human,
        :p_bg,:p_nick,:p_stage,:p_desc,:p_notes,:p_by
      )
    """)

    with _eng().begin() as cx:
        jft_has_allele = _col_exists(cx, "public", "join_fish_fluorescent_treatments", "allele_number")

        # ensure all ft_code parents
        if col_ft:
            ft_codes = sorted({str(x).strip() for x in df[col_ft].dropna().astype(str) if str(x).strip()})
            if ft_codes:
                cx.execute(text("""
                  INSERT INTO public.fluorescent_treatments (ft_code, ft_text, created_by)
                  SELECT code, ''::text, :by
                  FROM unnest(:codes::text[]) AS code
                  ON CONFLICT (ft_code) DO NOTHING
                """), {"codes": ft_codes, "by": created_by})

        for _, r in df.iterrows():
            ident = _identity_key(r)
            params = {
                "p_seed_batch_id": seed_batch_id,
                "p_identity_key":  ident,
                "p_dob":           r.get("birthday"),
                "p_name_human":    None,
                "p_bg":            (r.get("genetic_background") or None),
                "p_nick":          (_canon_nickname(r.get("nickname")) or None),
                "p_stage":         (r.get("line_building_stage") or None),
                "p_desc":          (r.get("description") or None),
                "p_notes":         None,
                "p_by":            created_by,
            }
            got = cx.execute(fn_upsert_fish, params).mappings().first() or {}
            fid = got.get("id") or got.get("fish_id")
            if not fid and got.get("fish_code"):
                fid = cx.execute(text("select id from public.fish where fish_code = :c"), {"c": got["fish_code"]}).scalar()
            fcode = got.get("fish_code")
            if not fid: continue
            inserted.append(dict(got))

            # markers: protein (fluor ± tag)
            ft_code = (str(r.get(col_ft)).strip() if col_ft and pd.notna(r.get(col_ft)) else "")
            fluor   = (str(r.get(col_flu)).strip() if col_flu and pd.notna(r.get(col_flu)) else "")
            tag     = (str(r.get(col_tag)).strip() if col_tag and pd.notna(r.get(col_tag)) else "")
            dye     = (str(r.get(col_dye)).strip() if col_dye and pd.notna(r.get(col_dye)) else "")
            nn      = _canon_nickname(str(r.get(col_nick)).strip()) if (col_nick and pd.notna(r.get(col_nick))) else ""
            zy      = (str(r.get(col_zyg)).strip() if (col_zyg and pd.notna(r.get(col_zyg))) else "")

            if ft_code:
                # ensure parent row carries a text if provided
                if "ft_text" in df.columns:
                    ft_text = str(r.get("ft_text") or "").strip()
                    if ft_text:
                        cx.execute(text("""
                          INSERT INTO public.fluorescent_treatments (ft_code, ft_text, created_by)
                          VALUES (:c,:t,:by)
                          ON CONFLICT (ft_code) DO UPDATE SET ft_text = COALESCE(NULLIF(EXCLUDED.ft_text,''), public.fluorescent_treatments.ft_text)
                        """), {"c": ft_code, "t": ft_text, "by": created_by})

                if fluor:
                    cx.execute(text("""
                      INSERT INTO public.ft_protein_markers (ft_code, fluor_code, tag_code)
                      VALUES (:ft, :flu, NULLIF(:tag,''))
                      ON CONFLICT (ft_code, COALESCE(tag_code,'∅'), fluor_code) DO NOTHING
                    """), {"ft": ft_code, "flu": fluor, "tag": tag})

                if dye:
                    cx.execute(text("""
                      INSERT INTO public.ft_dye_markers (ft_code, dye_code)
                      VALUES (:ft, :dye)
                      ON CONFLICT (ft_code, dye_code) DO NOTHING
                    """), {"ft": ft_code, "dye": dye})

                cx.execute(text("""
                  INSERT INTO public.join_fish_fluorescent_treatments
                    (fish_id, ft_code, allele_number, zygosity)
                  VALUES
                    (:fid, :ft, :allele, :zyg)
                  ON CONFLICT (fish_id, ft_code) DO UPDATE
                  SET  allele_number = COALESCE(EXCLUDED.allele_number, public.join_fish_fluorescent_treatments.allele_number),
                       zygosity      = COALESCE(EXCLUDED.zygosity,      public.join_fish_fluorescent_treatments.zygosity)
                """), {
                  "fid": fid,
                  "ft":  ft_code,
                  "allele": nn if jft_has_allele else None,
                  "zyg": zy or None,
                })
                linked += 1
            else:
                skipped += 1

st.success("Done.")

fish_codes = [row.get("fish_code") for row in inserted if row.get("fish_code")]
with _eng().begin() as cx:
    results = _fetch_vfish_rollup(cx, fish_codes)

if not results.empty:
    st.subheader("Fluorescent markers (rollup)")
    st.data_editor(
        results,
        hide_index=True,
        width="stretch",
        column_config={
            "fish_code":      cc.TextColumn("Fish code"),
            "markers":        cc.ListColumn("Markers"),
            "fluors":         cc.ListColumn("Fluors"),
            "tags":           cc.ListColumn("Tags"),
            "dyes":           cc.ListColumn("Dyes"),
        },
        key="fluor_rollup_v4",
    )
    st.download_button(
        "⬇︎ Download rollup (CSV)",
        data=results.to_csv(index=False).encode("utf-8"),
        file_name=f"fish_fluorescent_markers_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        type="secondary",
    )
else:
    st.info("No markers to show yet (import rows, then see rollup here).")