from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

# ── auth & gates ─────────────────────────────────────────────────────────────
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# ── std/3p ───────────────────────────────────────────────────────────────────
import io, os
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ✅ unified engine (env-driven, cached)
from carp_app.ui.lib.app_ctx import get_engine

PAGE_TITLE = "📤 Upload Plasmids (Upsert on code)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title(PAGE_TITLE)

# ------------------------------------------------------------------------------
# Example download
# ------------------------------------------------------------------------------
def _example_plasmids_bytes_name_mime():
    fp = Path("templates/examples/plasmids_example.xlsx")
    if fp.exists():
        data = fp.read_bytes()
        return data, fp.name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    cols = ["code", "name", "nickname", "fluors", "resistance",
            "supports_invitro_rna", "notes"]
    data = pd.DataFrame(columns=cols).to_csv(index=False).encode()
    return data, "plasmids_example.csv", "text/csv"

_data, _name, _mime = _example_plasmids_bytes_name_mime()
st.download_button(
    "⬇️ Download example — Plasmids",
    data=_data, file_name=_name, mime=_mime,
    help="Template columns for bulk upsert (conflict target = code).",
    type="secondary", width="stretch",
)

# ------------------------------------------------------------------------------
# DB setup (shared engine)
# ------------------------------------------------------------------------------
_ENGINE: Engine | None = None
def _get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

# ------------------------------------------------------------------------------
# Small utilities
# ------------------------------------------------------------------------------
def _list_table_columns(schema: str, table: str) -> list[str]:
    sql = """
      select column_name
      from information_schema.columns
      where table_schema=:schema and table_name=:table
      order by ordinal_position
    """
    with _get_engine().begin() as cx:
        df = pd.read_sql(text(sql), cx, params={"schema": schema, "table": table})
    return df["column_name"].tolist()

def _clean_df_for_table(df: pd.DataFrame, table_cols: list[str]) -> pd.DataFrame:
    keep = [c for c in df.columns if c in table_cols]
    out = df[keep].copy()
    # Trim strings and convert empty strings/NaN → None so SQLA sends NULL
    for c in out.columns:
        if pd.api.types.is_string_dtype(out[c]) or out[c].dtype == object:
            out[c] = out[c].where(out[c].notna(), None)
            out[c] = out[c].map(lambda x: x.strip() if isinstance(x, str) else x)
    return out.dropna(how="all", subset=keep)

# ------------------------------------------------------------------------------
# Upload controls
# ------------------------------------------------------------------------------
file = st.file_uploader("Upload plasmids file (.csv or .xlsx)", type=["csv", "xlsx"])
chunk_size = st.number_input("Batch size", 100, 5000, 1000, 100)

# Authenticated creator UUID (tight: uuid or None; never shell USER)
creator_uuid = getattr(user, "id", None)
created_by_uuid = str(creator_uuid) if creator_uuid else None

if not file:
    st.info("Choose a CSV/XLSX to begin.")
    st.stop()

# ------------------------------------------------------------------------------
# Read file
# ------------------------------------------------------------------------------
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
st.dataframe(df_raw.head(20), width="stretch", hide_index=True)
st.caption(f"{len(df_raw)} rows total")

# ------------------------------------------------------------------------------
# Prepare data against table schema
# ------------------------------------------------------------------------------
schema, table = "public", "plasmids"
table_cols = _list_table_columns(schema, table)
df = _clean_df_for_table(df_raw, table_cols)

# If table has created_by (uuid) and file didn't include one, fill with user uuid
if "created_by" in table_cols and "created_by" not in df.columns:
    df["created_by"] = created_by_uuid

if df.empty:
    st.warning("No overlapping columns between your file and the plasmids table.")
    st.stop()

# Normalize supports_invitro_rna → boolean if present
if "supports_invitro_rna" in df.columns:
    def _norm_flag(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return False
        s = str(v).strip().lower()
        return s in {"1","true","t","yes","y"}
    df["supports_invitro_rna"] = df["supports_invitro_rna"].map(_norm_flag)

st.success(f"Columns to load: {', '.join(df.columns)}")
st.caption(f"DB_URL → {os.getenv('DB_URL')}")
st.caption(f"CSV rows: {len(df)}")
st.caption(f"CSV codes sample: {', '.join(df.get('code', pd.Series(dtype=str)).astype(str).head(10).tolist())}")

# ------------------------------------------------------------------------------
# Upsert
# ------------------------------------------------------------------------------
if st.button("Upsert plasmids (on code)", type="primary", width="stretch"):
    ok = fail = rna_ok = rna_fail = 0

    # Build dynamic upsert SET clause using only columns present in both CSV and table
    cols = list(df.columns)
    cols_sql = ", ".join(cols)
    vals_sql = ", ".join([f":{c}" for c in cols])

    # Allow-list of columns that are safe to update on conflict
    updateable = [
        "name", "nickname", "fluors", "resistance",
        "notes", "created_by", "supports_invitro_rna"
    ]
    set_parts = [f"{c} = EXCLUDED.{c}" for c in cols if c in updateable and c in table_cols]
    if not set_parts:
        st.error("No updateable columns detected; add at least one of: " + ", ".join(updateable))
        st.stop()

    sql_upsert = f"""
        INSERT INTO public.plasmids ({cols_sql})
        VALUES ({vals_sql})
        ON CONFLICT (code)
        DO UPDATE SET {', '.join(set_parts)}
    """

    # Optional RNA ensure function (kept as-is; adjust signature if your function differs)
    sql_ensure = text("""
        select * from public.ensure_rna_for_plasmid(:plasmid_code, '-RNA', :rna_name, :by, :notes)
    """)

    # Execute
    recs: List[Dict[str, Any]] = df.where(pd.notna(df), None).to_dict(orient="records")
    codes_this_batch = [str(r.get("code") or "") for r in recs]

    with _get_engine().begin() as cx:
        try:
            cx.execute(text(sql_upsert), recs)  # executemany
            ok += len(recs)
        except Exception as e:
            fail += len(recs)
            st.error(f"❌ Upsert failed for {len(recs)} rows: {e}")

        # Ensure RNA rows where requested
        for r in recs:
            try:
                if r.get("supports_invitro_rna") is True:
                    code = (r.get("code") or "").strip()
                    if not code:
                        rna_fail += 1
                        continue
                    cx.execute(sql_ensure, {
                        "plasmid_code": code,
                        "rna_name": (r.get("name") or f"{code}-RNA"),
                        "by": created_by_uuid,
                        "notes": r.get("notes"),
                    })
                    rna_ok += 1
            except Exception as e:
                rna_fail += 1
                st.error(f"RNA ensure failed for {r.get('code')}: {e}")

    # Verify landed codes
    missing = []
    with _get_engine().begin() as cx:
        landed = pd.read_sql(
            text("select code from public.plasmids where code = any(:codes)"),
            cx, params={"codes": [c for c in codes_this_batch if c]},
        )["code"].astype(str).tolist()
    landed_set = set(landed)
    for c in codes_this_batch:
        if c and c not in landed_set:
            missing.append(c)

    st.success(f"Done. Upserted: {ok}. Failed: {fail}. RNA ensured: {rna_ok}. RNA failures: {rna_fail}.")
    if missing:
        st.warning(f"{len(missing)} codes not present after upsert. First 10: {missing[:10]}")