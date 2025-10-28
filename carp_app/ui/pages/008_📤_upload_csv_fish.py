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
from sqlalchemy import text, bindparam
from sqlalchemy.engine import Engine

from carp_app.ui.lib.app_ctx import get_engine
from carp_app.lib.time import utc_now

# ─────────────────────────────────────────────────────────────────────────────
# Page setup
# ─────────────────────────────────────────────────────────────────────────────
PAGE_TITLE = "CARP — New Fish from CSV"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)
st.caption(
    "Upserts by (seed_batch_id, name, birthday). Fish codes are assigned automatically. "
    "Founders (F0) may mint new alleles per rules. CSV must include the 'birthday' column."
)

# ─────────────────────────────────────────────────────────────────────────────
# DB engine (cached)
# ─────────────────────────────────────────────────────────────────────────────
_ENGINE: Optional[Engine] = None

def _get_engine() -> Engine:
    if _ENGINE is None:
        # rebind outer-scope variable without using 'global'
        globals()["_ENGINE"] = get_engine()
    return _ENGINE

# ─────────────────────────────────────────────────────────────────────────────
# CSV helpers
# ─────────────────────────────────────────────────────────────────────────────
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
    use_container_width=True,
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

# ─────────────────────────────────────────────────────────────────────────────
# Upload + preview
# ─────────────────────────────────────────────────────────────────────────────
uploaded = st.file_uploader("Upload fish CSV", type=["csv"])
if not uploaded:
    st.info("Choose a CSV to preview."); st.stop()

default_batch = Path(getattr(uploaded, "name", "")).stem
seed_batch_id = st.text_input("Seed batch ID", value=default_batch)

creator_uuid = getattr(user, "id", None)
created_by_uuid = str(creator_uuid) if creator_uuid else None

try:
    df = pd.read_csv(io.BytesIO(uploaded.getvalue()))
except Exception as e:
    st.error(f"Failed to read CSV: {e}")
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
st.dataframe(df.head(50), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# Column resolution
# ─────────────────────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────
def _coerce_strings(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _build_upsert_results_from_view(fish_codes: List[str]) -> pd.DataFrame:
    if not fish_codes:
        return pd.DataFrame()
    sql = text("""
        SELECT *
        FROM public.v_fish_rich
        WHERE fish_code = ANY(:codes)
        ORDER BY fish_code
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": fish_codes})
    return _coerce_strings(df)

sql_tank_exists = text("""
  SELECT 1 FROM public.tanks
  WHERE status='active' AND tank_code LIKE ('TANK(' || :fc || ')#%')
  LIMIT 1
""")
sql_ensure_tank = text("SELECT public.ensure_active_tank_for_fish(:fish_code)")
upsert_allele = text("""
  SELECT * FROM public.upsert_fish_allele_from_csv(:fish_id, :base_code, :allele_nickname)
""")

# ─────────────────────────────────────────────────────────────────────────────
# Upsert logic
# ─────────────────────────────────────────────────────────────────────────────
inserted: List[Dict[str, Any]] = []
if st.button("Upsert fish batch", type="primary", use_container_width=True):
    linked, skipped_links = 0, 0
    batch_fish_codes: List[str] = []

    fn_upsert = text("""
        SELECT * FROM public.upsert_fish_by_batch_name_dob(
            p_batch          => (:p_batch)::text,
            p_dob            => (:p_dob)::date,
            p_seed_batch_id  => (:p_seed_batch_id)::text,
            p_name           => (:p_name)::text,
            p_bg             => (:p_bg)::text,
            p_nick           => (:p_nick)::text,
            p_stage          => (:p_stage)::text,
            p_desc           => (:p_desc)::text,
            p_notes          => (:p_notes)::text,
            p_by             => (:p_by)::text
        )
    """).bindparams(
        bindparam("p_batch"), bindparam("p_dob"), bindparam("p_seed_batch_id"),
        bindparam("p_name"), bindparam("p_bg"), bindparam("p_nick"),
        bindparam("p_stage"), bindparam("p_desc"), bindparam("p_notes"), bindparam("p_by")
    )

    with _get_engine().begin() as cx:
        for _, r in df.iterrows():
            params = {
                "p_batch": seed_batch_id,
                "p_seed_batch_id": seed_batch_id,
                "p_dob": r.get("birthday"),
                "p_name": (r.get("name") or None),
                "p_bg": (r.get("genetic_background") or None),
                "p_nick": (r.get("nickname") or None),
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
            batch_fish_codes.append(fish_code)

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
                            text("""
                                UPDATE public.fish_transgene_alleles
                                   SET zygosity=:zyg
                                 WHERE fish_uuid=:fid AND transgene_base_code=:base
                            """),
                            {"zyg": zy, "fid": fish_id, "base": tg},
                        )
                    linked += 1
                else:
                    skipped_links += 1

    st.success(f"Upserted {len(inserted)} fish. Linked {linked} allele rows (skipped {skipped_links}).")

    if inserted:
        st.subheader("Upsert results (all cols from v_fish_rich)")
        results_df = _build_upsert_results_from_view(batch_fish_codes)
        st.caption(f"{len(results_df)} row(s) • columns: {', '.join(results_df.columns)}")

        if not results_df.empty:
            st.data_editor(
                results_df,
                hide_index=True,
                use_container_width=True,
                key="upsert_results_vfr_v1",
            )
            st.download_button(
                "⬇︎ Download upsert results (v_fish_rich.csv)",
                data=results_df.to_csv(index=False).encode("utf-8"),
                file_name=f"upsert_results_v_fish_rich_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
                type="secondary",
                mime="text/csv",
            )