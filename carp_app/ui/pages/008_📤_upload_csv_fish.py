from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

import io, os, re, math, hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import text, bindparam
from sqlalchemy.engine import Engine

from carp_app.ui.lib.app_ctx import get_engine
from carp_app.lib.time import utc_now

PAGE_TITLE = "CARP — New Fish from CSV"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)
st.caption("Upserts by explicit identity key; fish codes assigned automatically. CSV must include the 'birthday' column.")

_ENGINE: Optional[Engine] = None
def _get_engine() -> Engine:
    if _ENGINE is None:
        globals()["_ENGINE"] = get_engine()
    return _ENGINE

def _norm_str(v):
    if v is None: return ""
    s = str(v).strip().lower()
    return " ".join(s.split())

def _identity_key(r: pd.Series) -> str:
    parts = [
        _norm_str(r.get("name")),
        str(r.get("birthday") or "").strip(),
        _norm_str(r.get("genetic_background")),
        _norm_str(r.get("line_building_stage")),
        _norm_str(r.get("transgene_base_code")),
        _norm_str(r.get("allele_nickname")),
    ]
    base = " | ".join(parts)
    return base

def _example_fish_csv_bytes() -> bytes:
    example = pd.DataFrame([{
        "name": "",
        "nickname": "",
        "genetic_background": "casper",
        "line_building_stage": "F0",
        "description": "",
        "transgene_base_code": "pDQM005",
        "allele_nickname": "505",
        "zygosity": "",
        "birthday": "2025-01-15"
    }])
    return example.to_csv(index=False).encode("utf-8")

st.download_button(
    "⬇️ Example CSV (uses 'birthday')",
    data=_example_fish_csv_bytes(),
    file_name="fish_example.csv",
    mime="text/csv",
    type="secondary",
    width="stretch",
)

LEGACY_DATE_ALIASES = {"date_birth", "dob"}
_NUM_NICK_RE = re.compile(r"^[0-9]+(\.0+)?$")

def _canon_nickname(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if _NUM_NICK_RE.match(s):
        return re.sub(r"\.0+$", "", s)
    return s

def _parse_birthday(x) -> Optional[date]:
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        y, m, d = map(int, s.split("-"))
        return date(y, m, d)
    if re.match(r"^\d{8}$", s):
        y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8])
        return date(y, m, d)
    try:
        n = float(s)
        if not math.isnan(n):
            return date(1899, 12, 30) + timedelta(days=int(n))
    except Exception:
        pass
    try:
        from dateutil import parser
        return parser.parse(s).date()
    except Exception:
        return None

uploaded = st.file_uploader("Upload fish file (.csv or .xlsx)", type=["csv", "xlsx"])
if not uploaded:
    st.info("Choose a CSV to preview."); st.stop()

default_batch = Path(getattr(uploaded, "name", "")).stem
seed_batch_id = st.text_input("Seed batch ID", value=default_batch)

creator_uuid = getattr(user, "id", None)
created_by_uuid = str(creator_uuid) if creator_uuid else None

try:
    fname = (uploaded.name or "").lower()
    raw_bytes = uploaded.getvalue()
    if fname.endswith(".xlsx"):
        # Excel: let the user choose a sheet
        xls = pd.ExcelFile(io.BytesIO(raw_bytes))  # requires openpyxl
        sheet = st.selectbox("Choose worksheet", xls.sheet_names, index=0)
        df = xls.parse(sheet, dtype=object)
    else:
        # CSV: robust to BOM, keeps strings as-is
        df = pd.read_csv(io.BytesIO(raw_bytes), dtype=object)
except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

df.columns = [c.strip().lower() for c in df.columns]
for alias in LEGACY_DATE_ALIASES:
    if alias in df.columns and "birthday" not in df.columns:
        df.rename(columns={alias: "birthday"}, inplace=True)
if "birthday" not in df.columns:
    st.error("CSV must include a 'birthday' column (YYYY-MM-DD recommended).")
    st.stop()

df["birthday"] = df["birthday"].apply(_parse_birthday)
if "fish_code" in df.columns:
    df = df.drop(columns=["fish_code"])
for col in (
    "name", "nickname", "genetic_background", "line_building_stage",
    "description", "transgene_base_code", "allele_nickname", "zygosity", "notes"
):
    if col in df.columns:
        df[col] = df[col].fillna("").astype(str)

st.subheader("Preview (first 50 rows)")
st.dataframe(df.head(50), width="stretch", hide_index=True)

ALIASES = {
    "transgene_base_code": ["transgene_base_code","base_code","tg_base_code","transgene_base","tg_base"],
    "allele_nickname":     ["allele_nickname","allele_nick","allele_name","allele"],
    "zygosity":            ["zygosity","zyg","allele_zygosity"],
}

def _resolve_col(pdf: pd.DataFrame, keys: List[str]) -> Optional[str]:
    for k in keys:
        if k in pdf.columns:
            return k
    return None

col_tg   = _resolve_col(df, ALIASES["transgene_base_code"])
col_nick = _resolve_col(df, ALIASES["allele_nickname"])
col_zyg  = _resolve_col(df, ALIASES["zygosity"])

with st.expander("Detected allele-link columns"):
    st.write({
        "transgene_base_code": col_tg or "—",
        "allele_nickname": col_nick or "—",
        "zygosity": col_zyg or "—",
    })

def _coerce_strings(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _build_upsert_results_for_batch(seed_batch_id: str) -> pd.DataFrame:
    sql = text("""
        select v.*
        from public.v_fish_rich v
        join public.fish f on f.fish_code = v.fish_code
        where f.seed_batch_id = :bid
        order by v.fish_code
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"bid": seed_batch_id})
    return _coerce_strings(df)

sql_tank_exists = text("""
  select 1 from public.tanks
  where status='active' and tank_code like ('TANK(' || :fc || ')#%')
  limit 1
""")
sql_ensure_tank = text("select public.ensure_active_tank_for_fish(:fish_code)")
upsert_allele = text("select * from public.upsert_fish_allele_from_csv(:fish_id, :base_code, :allele_nickname)")

inserted: List[Dict[str, Any]] = []
if st.button("Upsert fish batch", type="primary", width="stretch"):
    linked, skipped_links = 0, 0

    fn_upsert = text("""
      select * from public.upsert_fish_by_identity(
        :p_seed_batch_id,
        :p_identity_key,
        :p_dob,
        :p_name_human,
        :p_bg,
        :p_nick,
        :p_stage,
        :p_desc,
        :p_notes,
        :p_by
      )
    """)

    with _get_engine().begin() as cx:
        for _, r in df.iterrows():
            ident = _identity_key(r)
            human_name = (r.get("name") or None)
            params = {
                "p_seed_batch_id": seed_batch_id,
                "p_identity_key": ident,
                "p_dob": r.get("birthday"),
                "p_name_human": human_name,
                "p_bg": (r.get("genetic_background") or None),
                "p_nick": (_canon_nickname(r.get("nickname")) or None),
                "p_stage": (r.get("line_building_stage") or None),
                "p_desc": (r.get("description") or None),
                "p_notes": (r.get("notes") or None),
                "p_by": (created_by_uuid or getattr(user, "email", None) or os.environ.get("USER") or "system"),
            }
            got = cx.execute(fn_upsert, params).mappings().first() or {}
            if not got:
                continue
            fish_id, fish_code = got.get("fish_uuid"), got.get("fish_code")
            inserted.append(dict(got))

            if not fish_id:
                raise RuntimeError(f"Upsert failed for {fish_code or '(unknown)'} — no fish_uuid returned")

            if not cx.execute(sql_tank_exists, {"fc": fish_code}).fetchone():
                cx.execute(sql_ensure_tank, {"fish_code": fish_code})

            if col_tg:
                tg = (str(r.get(col_tg)).strip() if pd.notna(r.get(col_tg)) else "")
                raw_nn = str(r.get(col_nick)).strip() if (col_nick and pd.notna(r.get(col_nick))) else ""
                nn = _canon_nickname(raw_nn)
                zy = (str(r.get(col_zyg)).strip() if (col_zyg and pd.notna(r.get(col_zyg))) else "")
                if tg:
                    cx.execute(upsert_allele, {"fish_id": fish_id, "base_code": tg, "allele_nickname": nn})
                    if zy:
                        cx.execute(
                            text("update public.fish_transgene_alleles set zygosity=:zyg where fish_uuid=:fid and transgene_base_code=:base"),
                            {"zyg": zy, "fid": fish_id, "base": tg},
                        )
                    linked += 1
                else:
                    skipped_links += 1

    st.success(f"Upserted {len(inserted)} fish. Linked {linked} allele rows (skipped {skipped_links}).")

    results_df = _build_upsert_results_for_batch(seed_batch_id)
    st.caption(f"{len(results_df)} row(s) • columns: {', '.join(results_df.columns)}")
    if not results_df.empty:
        st.data_editor(results_df, hide_index=True, width="stretch", key="upsert_results_vfr_v1")
        st.download_button(
            "⬇︎ Download upsert results (v_fish_rich.csv)",
            data=results_df.to_csv(index=False).encode("utf-8"),
            file_name=f"upsert_results_v_fish_rich_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
            type="secondary",
            mime="text/csv",
        )