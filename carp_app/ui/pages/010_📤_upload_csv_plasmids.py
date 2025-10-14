from __future__ import annotations
from supabase.ui.auth_gate import require_auth
sb, session, user = require_auth()

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import io, os
from typing import List, Dict, Any
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# 🔒 Optional unlock
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

PAGE_TITLE = "📤 Upload Plasmids (Upsert on code)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")

def _example_plasmids_bytes_name_mime():
    fp = Path("templates/examples/plasmids_example.xlsx")
    if fp.exists():
        data = fp.read_bytes()
        return data, fp.name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    import pandas as pd
    cols = ["plasmid_name","element_name","concentration","units","notes"]
    data = pd.DataFrame(columns=cols).to_csv(index=False).encode()
    return data, "plasmids_example.csv", "text/csv"



_data, _name, _mime = _example_plasmids_bytes_name_mime()
st.download_button(
    "⬇️ Download example — Plasmids",
    data=_data,
    file_name=_name,
    mime=_mime,
    help="Exact plasmids example from the repo.",
    type="secondary",
    width='stretch',
)



def _expected_plasmid_cols() -> list[str]:
    ex_xlsx = Path("templates/examples/plasmids_example.xlsx")
    if ex_xlsx.exists():
        try:
            return list(pd.read_excel(ex_xlsx, nrows=0, engine="openpyxl").columns)
        except Exception:
            pass
    return ["plasmid_name","element_name","concentration","units","notes"]

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

# ------------------------ DB setup ------------------------
_ENGINE = None
def _get_engine():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    _ENGINE = create_engine(url, future=True)
    return _ENGINE

# ------------------------ utilities ------------------------
def _list_table_columns(schema: str, table: str) -> List[str]:
    sql = """
      select column_name
      from information_schema.columns
      where table_schema=:schema and table_name=:table
      order by ordinal_position
    """
    with _get_engine().begin() as cx:
        df = pd.read_sql(text(sql), cx, params={"schema": schema, "table": table})
    return df["column_name"].tolist()

def _clean_df_for_table(df: pd.DataFrame, table_cols: List[str]) -> pd.DataFrame:
    keep = [c for c in df.columns if c in table_cols]
    out = df[keep].copy()
    for c in out.columns:
        if pd.api.types.is_string_dtype(out[c]):
            out[c] = out[c].astype(object).where(out[c].notna(), None)
            out[c] = out[c].map(lambda x: x.strip() if isinstance(x, str) else x)
    out = out.dropna(how="all", subset=keep)
    return out

def _chunked_records(df: pd.DataFrame, size: int = 500):
    n = len(df)
    for i in range(0, n, size):
        yield df.iloc[i:i+size]

# ------------------------ UI ------------------------
file = st.file_uploader("Upload plasmids file (.csv or .xlsx)", type=["csv", "xlsx"])
chunk_size = st.number_input("Batch size", 100, 5000, 1000, 100)
created_by_default = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
created_by = st.text_input("Created by (default if missing)", value=created_by_default)

if not file:
    st.info("Choose a CSV/XLSX to begin.")
    st.stop()

# ------------------------ Read file ------------------------
try:
    if file.name.lower().endswith(".xlsx"):
        df_raw = pd.read_excel(io.BytesIO(file.read()), dtype=object)
    else:
        df_raw = pd.read_csv(file, dtype=object)
except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

df_raw.columns = [c.strip() for c in df_raw.columns]
st.subheader("Preview of uploaded data")
st.dataframe(df_raw.head(20), use_container_width=True, hide_index=True)
st.caption(f"{len(df_raw)} rows total")

# ------------------------ Prepare data ------------------------
schema, table = "public", "plasmids"
table_cols = _list_table_columns(schema, table)
df = _clean_df_for_table(df_raw, table_cols)

# auto add created_by
if "created_by" in table_cols and "created_by" not in df.columns:
    df["created_by"] = created_by

if df.empty:
    st.warning("No overlapping columns between your file and the plasmids table.")
    st.stop()

st.success(f"Columns to load: {', '.join(df.columns)}")

# ------------------------ Load ------------------------
# normalize supports_invitro_rna → boolean
if "supports_invitro_rna" in df.columns:
    def _norm_flag(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return False
        s = str(v).strip().lower()
        return s in {"1","true","yes","y","t"}
    df["supports_invitro_rna"] = df["supports_invitro_rna"].map(_norm_flag)

# quick debug
st.caption(f"DB_URL → {os.getenv('DB_URL')}")
st.caption(f"CSV rows: {len(df)}")
st.caption(f"CSV codes sample: {', '.join(df.get('code', pd.Series(dtype=str)).astype(str).head(10).tolist())}")
st.caption(f"supports_invitro_rna truthy count: {int(df.get('supports_invitro_rna', pd.Series()).astype(str).str.lower().isin(['1','true','t','yes','y']).sum())}")

if st.button("Upsert plasmids (on code)", type="primary"):
    total = len(df)
    ok, fail = 0, 0
    rna_ok, rna_fail = 0, 0

    # normalize supports_invitro_rna → boolean once
    if "supports_invitro_rna" in df.columns:
        def _norm_flag(v):
            if v is None or (isinstance(v, float) and pd.isna(v)): return False
            s = str(v).strip().lower()
            return s in {"1","true","t","yes","y"}
        df["supports_invitro_rna"] = df["supports_invitro_rna"].map(_norm_flag)

    # upsert SQL
    cols = list(df.columns)
    cols_sql = ", ".join(cols)
    vals_sql = ", ".join([f":{c}" for c in cols])
    set_parts = [
        "name = EXCLUDED.name",
        "nickname = EXCLUDED.nickname",
        "fluors = EXCLUDED.fluors",
        "resistance = EXCLUDED.resistance",
        "notes = EXCLUDED.notes",
        "created_by = EXCLUDED.created_by",
    ]
    if "supports_invitro_rna" in cols:
        set_parts.append("supports_invitro_rna = EXCLUDED.supports_invitro_rna")

    sql = f"""
        INSERT INTO public.plasmids ({cols_sql})
        VALUES ({vals_sql})
        ON CONFLICT (code)
        DO UPDATE SET {', '.join(set_parts)}
    """
    sql_ensure = text("select * from public.ensure_rna_for_plasmid(:plasmid_code, '-RNA', :rna_name, :by, :notes)")

    codes_this_batch = df["code"].astype(str).tolist()

    bar = st.progress(0.0)
    with _get_engine().begin() as cx:
        # 2a) perform upsert
        recs: List[Dict[str, Any]] = df.where(pd.notna(df), None).to_dict(orient="records")
        try:
            cx.execute(text(sql), recs)
            ok += len(recs)
        except Exception as e:
            fail += len(recs)
            st.error(f"❌ Upsert failed for {len(recs)} rows: {e}")

        # 2b) ensure RNA where requested
        user_by = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
        for r in recs:
            if r.get("supports_invitro_rna") is True:
                code = (r.get("code") or "").strip()
                if not code:
                    rna_fail += 1
                    continue
                try:
                    cx.execute(sql_ensure, {
                        "plasmid_code": code,
                        "rna_name": (r.get("name") or f"{code}-RNA"),
                        "by": user_by,
                        "notes": r.get("notes"),
                    })
                    rna_ok += 1
                except Exception as e:
                    rna_fail += 1
                    st.error(f"RNA ensure failed for {code}: {e}")

        bar.progress(1.0)

    # 2c) verify which codes landed (by exact code) and show missing
    missing = []
    with _get_engine().begin() as cx:
        landed = pd.read_sql(
            text("select code from public.plasmids where code = ANY(:codes)"),
            cx, params={"codes": codes_this_batch},
        )["code"].astype(str).tolist()
    landed_set = set(landed)
    for c in codes_this_batch:
        if c not in landed_set:
            missing.append(c)

    st.success(f"Done. Plasmids upserted: {ok}. Failed: {fail}. RNAs ensured: {rna_ok}. RNA failures: {rna_fail}.")
    if missing:
        st.warning(f"{len(missing)} codes not present in table after upsert. First 10: {missing[:10]}")
