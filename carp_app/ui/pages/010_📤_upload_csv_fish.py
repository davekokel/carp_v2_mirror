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

import io, os, re, math
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.ui.lib.app_ctx import get_engine  # use shared, env-driven engine

PAGE_TITLE = "CARP — New Fish from CSV"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)
st.caption(
    "Upserts by (seed_batch_id, name, birthday). Fish codes are assigned automatically. "
    "Founders (F0) may mint new alleles per rules. CSV must include the 'birthday' column."
)

_ENGINE: Optional[Engine] = None
def _get_engine() -> Engine:
    global _ENGINE
    if _ENGINE:
        return _ENGINE
    _ENGINE = get_engine()
    return _ENGINE

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
        "birthday": "2025-01-15",
        "created_by": os.environ.get("USER") or os.environ.get("USERNAME") or "system",
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
    if s == "":
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        y, m, d = map(int, s.split("-")); return date(y, m, d)
    if re.match(r"^\d{8}$", s):
        y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8]); return date(y, m, d)
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

uploaded = st.file_uploader("Upload fish CSV", type=["csv"])
if not uploaded:
    st.info("Choose a CSV to preview."); st.stop()

default_batch = Path(getattr(uploaded, "name", "")).stem
seed_batch_id = st.text_input("Seed batch ID", value=default_batch)
created_by = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"

try:
    df = pd.read_csv(io.BytesIO(uploaded.getvalue()))
except Exception as e:
    st.error(f"Failed to read CSV: {e}"); st.stop()

df.columns = [c.strip().lower() for c in df.columns]
for alias in LEGACY_DATE_ALIASES:
    if alias in df.columns and "birthday" not in df.columns:
        df.rename(columns={alias: "birthday"}, inplace=True)
if "birthday" not in df.columns:
    st.error("CSV must include a 'birthday' column (YYYY-MM-DD recommended)."); st.stop()

df["birthday"] = df["birthday"].apply(_parse_birthday)
if "fish_code" in df.columns:
    df = df.drop(columns=["fish_code"])
for col in (
    "name","nickname","genetic_background","line_building_stage","description",
    "transgene_base_code","allele_nickname","zygosity","created_by","notes"
):
    if col in df.columns:
        df[col] = df[col].fillna("").astype(str)

df_preview = df.copy()
df_preview["_preview_birthday"] = df_preview["birthday"].apply(lambda d: d.isoformat() if isinstance(d, date) else "")
st.subheader("Preview (first 50 rows)")
st.dataframe(df_preview.head(50), width="stretch", hide_index=True)

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

def _build_upsert_results(fish_codes: List[str]) -> pd.DataFrame:
    if not fish_codes:
        return pd.DataFrame(columns=[
            "fish_code","name","nickname","genetic_background",
            "transgene_base_code","allele_number","allele_name","allele_nickname",
            "transgene_pretty","tank_code","tank_status","genotype_rollup"
        ])
    sql = text("""
      with alleles as (
        select
          f.fish_code,
          fta.transgene_base_code,
          fta.allele_number,
          ta.allele_name,
          r.allele_nickname::text as allele_nickname,
          ('Tg(' || fta.transgene_base_code || ')' || ta.allele_name) as transgene_pretty
        from public.fish f
        left join public.fish_transgene_alleles fta on fta.fish_id = f.id
        left join public.transgene_alleles ta
          on ta.transgene_base_code = fta.transgene_base_code
         and ta.allele_number       = fta.allele_number
        left join public.transgene_allele_registry r
          on r.transgene_base_code  = fta.transgene_base_code
         and r.allele_number        = fta.allele_number
        where f.fish_code = any(:codes)
      ),
      tanks as (
        select
          f.fish_code,
          vt.tank_code::text as tank_code,
          vt.status::text    as tank_status
        from public.fish f
        left join public.v_tanks vt on vt.fish_code = f.fish_code
        where f.fish_code = any(:codes)
      ),
      geno as (
        select
          a.fish_code,
          string_agg(a.transgene_pretty, '; ' order by a.transgene_pretty) as genotype_rollup
        from alleles a
        group by a.fish_code
      )
      select
        f.fish_code,
        f.name,
        f.nickname,
        f.genetic_background,
        a.transgene_base_code,
        a.allele_number,
        a.allele_name,
        a.allele_nickname,
        a.transgene_pretty,
        t.tank_code,
        t.tank_status,
        g.genotype_rollup
      from public.fish f
      left join alleles a on a.fish_code = f.fish_code
      left join tanks  t on t.fish_code = f.fish_code
      left join geno   g on g.fish_code = f.fish_code
      where f.fish_code = any(:codes)
      order by f.fish_code, a.allele_number nulls last
    """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": fish_codes})

inserted: List[Dict[str, Any]] = []
if st.button("Upsert fish batch", type="primary", width="stretch"):
    linked = 0
    skipped_links = 0

    fn_upsert = text("""
        select * from public.upsert_fish_by_batch_name_dob(
            :batch, :name, :dob, :bg, :nick, :stage, :desc, :notes, :by
        )
    """)
    upsert_allele = text("""
        select * from public.upsert_fish_allele_from_csv(:fish_id, :base_code, :allele_nickname)
    """)

    batch_fish_codes: List[str] = []

    with _get_engine().begin() as cx:
        for _, r in df.iterrows():
            params = dict(
                batch = seed_batch_id,
                name  = (r.get("name") or None),
                dob   = r.get("birthday"),
                bg    = (r.get("genetic_background") or None),
                nick  = (r.get("nickname") or None),
                stage = (r.get("line_building_stage") or None),
                desc  = (r.get("description") or None),
                notes = (r.get("notes") or None),
                by    = (r.get("created_by") or created_by),
            )
            got = cx.execute(fn_upsert, params).mappings().first()
            if not got:
                continue
            inserted.append(dict(got))
            batch_fish_codes.append(got["fish_code"])
            fish_id = got["fish_id"]

            if col_tg:
                tg = (str(r.get(col_tg)).strip() if pd.notna(r.get(col_tg)) else "")
                raw_nn = str(r.get(col_nick)).strip() if (col_nick and pd.notna(r.get(col_nick))) else ""
                nn = _canon_nickname(raw_nn)
                zy = (str(r.get(col_zyg)).strip() if (col_zyg and pd.notna(r.get(col_zyg))) else "")

                if tg:
                    cx.execute(upsert_allele, {
                        "fish_id": fish_id,
                        "base_code": tg,
                        "allele_nickname": nn,
                    })
                    if zy:
                        cx.execute(
                            text("""update public.fish_transgene_alleles
                                    set zygosity=:zyg
                                    where fish_id=:fid and transgene_base_code=:base"""),
                            {"zyg": zy, "fid": fish_id, "base": tg}
                        )
                    linked += 1
                else:
                    skipped_links += 1

    st.success(f"Upserted {len(inserted)} fish. Linked {linked} allele rows (skipped {skipped_links}).")

    if inserted:
        st.subheader("Upsert results")
        results_df = _build_upsert_results(batch_fish_codes)

        for col in ("allele_nickname","allele_name","transgene_pretty","tank_code","tank_status"):
            if col in results_df.columns:
                results_df[col] = results_df[col].astype("string")

        cols_exact = [
            "fish_code",
            "name",
            "nickname",
            "genetic_background",
            "transgene_base_code",
            "allele_number",
            "allele_name",
            "allele_nickname",
            "transgene_pretty",
            "genotype_rollup",
            "tank_code",
            "tank_status",
        ]
        for c in cols_exact:
            if c not in results_df.columns:
                results_df[c] = pd.Series(dtype="string")

        show = results_df[cols_exact].rename(columns={
            "fish_code":           "Fish code",
            "name":                "Fish name",
            "nickname":            "Fish nickname",
            "genetic_background":  "Genetic background",
            "transgene_base_code": "Transgene base code",
            "allele_number":       "Allele number",
            "allele_name":         "Allele name",
            "allele_nickname":     "Allele nickname",
            "transgene_pretty":    "Transgene pretty",
            "genotype_rollup":     "Genotype rollup",
            "tank_code":           "Tank code",
            "tank_status":         "Tank status",
        })

        st.dataframe(show, width="stretch", hide_index=True)