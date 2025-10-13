from __future__ import annotations
from supabase.ui.auth_gate import require_auth
sb, session, user = require_auth()
from supabase.ui.email_otp_gate import require_email_otp
require_email_otp()

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import io, os, re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

PAGE_TITLE = "CARP — New Fish from CSV"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")

def _example_fish_csv_bytes():
    fp = Path("templates/examples/fish_example.csv")
    try:
        if fp.exists():
            return fp.read_bytes()
    except Exception:
        pass
    import pandas as pd
    cols = ["name","nickname","date_birth","genetic_background","line_building_stage","description","transgene_base_code","allele_nickname","zygosity","created_by"]
    return pd.DataFrame(columns=cols).to_csv(index=False).encode()



st.download_button(
    "⬇️ Download example — Fish CSV",
    data=_example_fish_csv_bytes(),
    file_name="fish_example.csv",
    mime="text/csv",
    help="Exact seedkit rows; use as your template.",
    type="secondary",
    width='stretch',
)



def _expected_fish_cols() -> list[str]:
    ex = Path("templates/examples/fish_example.csv")
    if ex.exists():
        try:
            return list(pd.read_csv(ex, nrows=0).columns)
        except Exception:
            pass
    return [
        "name","nickname","date_birth","genetic_background","line_building_stage",
        "description","transgene_base_code","allele_nickname","zygosity","created_by",
    ]

def _validate_headers(got: list[str], expected: list[str]) -> tuple[bool,str,list[str]]:
    got_set, exp_set = set(got), set(expected)
    missing = [c for c in expected if c not in got_set]
    extra   = [c for c in got if c not in exp_set]
    if missing:
        msg = "Missing required columns: " + ", ".join(missing)
        if extra:
            msg += " • Extra columns: " + ", ".join(extra)
        return False, msg, expected
    if got != expected:
        msg = "Columns present but out of order; preview re-ordered to match template."
    else:
        msg = "Columns match the template."
    return True, msg, expected

st.title(PAGE_TITLE)
st.caption("Upserts by (seed_batch_id, name, date_birth); assigns fish_code automatically. Founders with base code and no nickname will allocate a **new** allele.")

_ENGINE: Optional[Engine] = None
def _get_engine() -> Engine:
    global _ENGINE
    if _ENGINE:
        return _ENGINE
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    _ENGINE = create_engine(url, future=True)
    return _ENGINE

def parse_date_birth(x):
    if x is None:
        return None
    import math
    s = str(x).strip()
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            y,m,d = map(int,s.split("-")); return date(y,m,d)
        if re.match(r"^\d{8}$", s):
            y,m,d = int(s[:4]),int(s[4:6]),int(s[6:8]); return date(y,m,d)
        n = float(s)
        if not math.isnan(n):
            return date(1899,12,30)+timedelta(days=int(n))
    except Exception:
        pass
    try:
        from dateutil import parser; return parser.parse(s).date()
    except Exception:
        return None

uploaded = st.file_uploader("CSV file", type=["csv"])
if not uploaded:
    st.info("Choose a CSV to preview.")
    st.stop()

default_batch = Path(getattr(uploaded,"name","")).stem
seed_batch_id = st.text_input("Seed batch ID", value=default_batch)
created_by = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"

# Read CSV once (dates parsed)
try:
    df = pd.read_csv(io.BytesIO(uploaded.getvalue()), converters={"date_birth":parse_date_birth})
except Exception as e:
    st.error(f"Failed to read CSV: {e}")
    st.stop()

# Normalize headers (trim)
df.columns = [c.strip() for c in df.columns]

# Ignore incoming fish_code — DB generates it
if "fish_code" in df.columns:
    df = df.drop(columns=["fish_code"])

# Show preview (make date printable)
if "date_birth" in df.columns:
    df["_preview_date_birth"] = df["date_birth"].apply(lambda d: d.isoformat() if isinstance(d,date) else d)
st.subheader("Preview")
st.dataframe(df.head(50), use_container_width=True, hide_index=True)

# Resolve potential link columns (any alias)
ALIASES = {
    "transgene_base_code": ["transgene_base_code","base_code","tg_base_code","transgene_base","tg_base"],
    "allele_nickname":     ["allele_nickname","allele_nick","allele_name","allele"],
    "zygosity":            ["zygosity","zyg","allele_zygosity"],
}
def _col(df: pd.DataFrame, keys: list[str]) -> Optional[str]:
    for k in keys:
        if k in df.columns: return k
    return None

col_tg   = _col(df, ALIASES["transgene_base_code"])
col_nick = _col(df, ALIASES["allele_nickname"])
col_zyg  = _col(df, ALIASES["zygosity"])

with st.expander("Detected link columns"):
    st.write({
        "transgene_base_code": col_tg or "—",
        "allele_nickname": col_nick or "—",
        "zygosity": col_zyg or "—",
    })

if st.button("Upsert fish batch", type="primary"):
    inserted: list[dict] = []
    linked = 0
    skipped_links = 0

    fn_upsert = text("select * from public.upsert_fish_by_batch_name_dob(:batch,:name,:dob,:bg,:nick,:stage,:desc,:notes,:by)")
    fn_ensure = text("select * from public.ensure_transgene_allele(:transgene_base_code, :allele_nickname)")
    stmt_link = text("""
        insert into public.fish_transgene_alleles(fish_id, transgene_base_code, allele_number, zygosity)
        values (:fish_id, :base, :allele_number, :zyg)
        on conflict (fish_id, transgene_base_code) do update
          set allele_number = EXCLUDED.allele_number,
              zygosity      = COALESCE(EXCLUDED.zygosity, public.fish_transgene_alleles.zygosity)
    """)

    with _get_engine().begin() as cx:
        for _, r in df.iterrows():
            # 1) Upsert the fish by (batch, name, date_birth)
            params = dict(
                batch = seed_batch_id,
                name  = r.get("name"),
                dob   = r.get("date_birth"),
                bg    = r.get("genetic_background"),
                nick  = r.get("nickname"),
                stage = r.get("line_building_stage"),
                desc  = r.get("description"),
                notes = r.get("notes"),
                by    = created_by
            )
            got = cx.execute(fn_upsert, params).mappings().first()
            if not got:
                continue
            inserted.append(dict(got))
            fish_id = got["fish_id"]

            # 2) Optional allele linking (Option A behavior)
            if col_tg:
                tg  = (str(r.get(col_tg)).strip()   if pd.notna(r.get(col_tg))   else "")
                nn  = (str(r.get(col_nick)).strip() if (col_nick and pd.notna(r.get(col_nick))) else "")
                # normalize numeric-like nicknames from CSV (e.g., '302.0' -> '302')
                if nn and (nn.strip().isdigit() or nn.strip().endswith('.0')):
                    try:
                        nn = str(int(float(nn)))
                    except Exception:
                        pass
                zy  = (str(r.get(col_zyg)).strip()  if (col_zyg and pd.notna(r.get(col_zyg)))  else "")

                stg_raw = r.get("line_building_stage")
                stg_val = (str(stg_raw).strip().lower() if pd.notna(stg_raw) and stg_raw is not None else "")

                # If founder/F0 with base code but blank nickname → mint a new allele
                if tg and not nn and stg_val in {"founder", "f0"}:
                    nn = "new"

                if tg:
                    alle = cx.execute(fn_ensure, {"transgene_base_code": tg, "allele_nickname": nn or None}).mappings().first()
                    if alle and alle.get("ret_allele_number") is not None:
                        cx.execute(stmt_link, {
                            "fish_id": fish_id,
                            "base": tg,
                            "allele_number": int(alle["ret_allele_number"]),
                            "zyg": zy or None
                        })
                        linked += 1
                    else:
                        skipped_links += 1

    st.success(f"Upserted {len(inserted)} fish. Linked {linked} allele rows (skipped {skipped_links}).")

    if inserted:
        st.subheader("Upsert results")

        # preserve order of just-upserted codes
        codes = [row["fish_code"] for row in inserted if row.get("fish_code")]
        cols_std = [
            "fish_code","name","nickname","genotype","genetic_background","stage",
            "date_birth","age_days","created_at","created_by","batch_display",
            "treatments_rollup","n_living_tanks"
        ]

        # Try standard view first
        try:
            with _get_engine().begin() as cx:
                df_std = pd.read_sql(
                    text("select * from public.vw_fish_standard where fish_code = any(:codes)"),
                    cx, params={"codes": codes}
                )
        except Exception:
            # Fallback if vw_fish_standard isn't present yet
            with _get_engine().begin() as cx:
                df_std = pd.read_sql(text("""
                select
                    v.fish_code,
                    v.name,
                    v.nickname,
                    v.genotype_print                        as genotype,
                    coalesce(v.genetic_background_print, v.genetic_background) as genetic_background,
                    coalesce(v.line_building_stage, v.line_building_stage_print) as stage,
                    v.date_birth_print::date                 as date_birth,
                    null::int                                as age_days,
                    v.created_at,
                    v.created_by_enriched                    as created_by,
                    coalesce(v.batch_label, v.seed_batch_id) as batch_display,
                    null::text                               as treatments_rollup,
                    null::int                                as n_living_tanks
                from public.vw_fish_overview_with_label v
                where v.fish_code = any(:codes)
                """), cx, params={"codes": codes})

        # restore input order
        order = {c:i for i, c in enumerate(codes)}
        if "fish_code" in df_std.columns:
            df_std["__ord"] = df_std["fish_code"].map(order).fillna(len(order)).astype(int)
            df_std = df_std.sort_values("__ord").drop(columns="__ord")

        # ensure all expected columns exist (tolerant)
        for c in cols_std:
            if c not in df_std.columns:
                df_std[c] = None

        st.dataframe(df_std[cols_std], use_container_width=True, hide_index=True)
