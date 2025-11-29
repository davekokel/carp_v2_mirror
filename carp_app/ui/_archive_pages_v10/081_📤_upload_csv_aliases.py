# carp_app/ui/pages/080_📤_upload_csv_aliases.py
from __future__ import annotations

import io, pathlib, sys
from typing import Optional, List, Dict

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
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Upload Aliases", page_icon="📤", layout="wide")
st.title("📤 Upload Aliases")
st.caption(
    "CSV/XLSX columns: **target_kind, target_code, alias**. "
    "Allowed kinds: fluor, tag, dye, rna, plasmid, fish, tank, cross, clutch_inst, treated_clutch. "
    "Import is idempotent; duplicates are ignored."
)

_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

def _example_csv() -> bytes:
    df = pd.DataFrame([
        {"target_kind":"fluor","target_code":"mYongHong","alias":"mYH"},
        {"target_kind":"fluor","target_code":"mYongHong","alias":"mScarlet3-H"},
        {"target_kind":"fluor","target_code":"mStayGold","alias":"mSG"},
        {"target_kind":"tag","target_code":"h2b","alias":"H2B"},
        {"target_kind":"rna","target_code":"RNA(MGCO-01)","alias":"YH1"},
        {"target_kind":"plasmid","target_code":"pDQM051","alias":"pDQM-51"},
    ])
    return df.to_csv(index=False).encode("utf-8")

st.download_button("⬇︎ Example alias.csv", data=_example_csv(),
                   file_name="alias_example.csv", mime="text/csv", use_container_width=True)

uploaded = st.file_uploader("Upload alias file (.csv or .xlsx)", type=["csv","xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin."); st.stop()

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
    st.error(f"Failed to read file: {e}"); st.stop()

df = df.copy()
df.columns = [str(c).strip().lower() for c in df.columns]
aliases: Dict[str, List[str]] = {
    "target_kind": ["target_kind","kind","entity_kind","type"],
    "target_code": ["target_code","code","entity_code","id"],
    "alias":       ["alias","alias_name","aka","synonym"],
}
ren: Dict[str, str] = {}
for tgt, alts in aliases.items():
    if tgt in df.columns: continue
    for a in alts:
        if a in df.columns:
            ren[a] = tgt
            break
if ren:
    df.rename(columns=ren, inplace=True)

required = {"target_kind","target_code","alias"}
missing = required - set(df.columns)
if missing:
    st.error("Missing required columns: " + ", ".join(sorted(missing))); st.stop()

df = df[list(required)].fillna("").astype(str)
df["target_kind"] = df["target_kind"].str.strip().str.lower()
df["target_code"] = df["target_code"].str.strip()
df["alias"] = df["alias"].str.strip()

st.subheader("Preview")
st.dataframe(df.head(50), use_container_width=True, hide_index=True)
st.caption(f"{len(df)} rows")

allowed = {"fluor","tag","dye","rna","plasmid","fish","tank","cross","clutch_inst","treated_clutch"}
bad_kinds = sorted(set(df["target_kind"]) - allowed)
if bad_kinds:
    st.error("Unknown target_kind values: " + ", ".join(bad_kinds))
    st.stop()

df = df[(df["target_kind"]!="") & (df["target_code"]!="") & (df["alias"]!="")]
if df.empty:
    st.info("Nothing to insert."); st.stop()

if not st.button("Process aliases", type="primary", use_container_width=True):
    st.stop()

inserted = 0
unknown_rows = pd.DataFrame(columns=["target_kind","target_code","alias"])

sql_stage = """
CREATE TEMP TABLE _alias_csv(target_kind text, target_code text, alias text);
"""
sql_copy_values = "INSERT INTO _alias_csv(target_kind, target_code, alias) VALUES (:k, :c, :a);"

sql_insert = """
WITH norm AS (
  SELECT lower(btrim(target_kind)) AS k, btrim(target_code) AS code, btrim(alias) AS alias FROM _alias_csv
),
res AS (
  SELECT 'fluor'::alias_target_kind AS kind, f.id AS target_id, n.alias, n.k, n.code
  FROM norm n JOIN public.fluors f ON lower(f.fluor_code)=lower(n.code) WHERE n.k='fluor'
  UNION ALL
  SELECT 'tag', t.id, n.alias, n.k, n.code
  FROM norm n JOIN public.tags t ON lower(t.tag_code)=lower(n.code) WHERE n.k='tag'
  UNION ALL
  SELECT 'dye', d.id, n.alias, n.k, n.code
  FROM norm n JOIN public.dyes d ON lower(d.dye_code)=lower(n.code) WHERE n.k='dye'
  UNION ALL
  SELECT 'rna', r.id, n.alias, n.k, n.code
  FROM norm n JOIN public.rnas r ON lower(r.rna_code)=lower(n.code) WHERE n.k='rna'
  UNION ALL
  SELECT 'plasmid', p.id, n.alias, n.k, n.code
  FROM norm n JOIN public.plasmids p ON lower(p.code)=lower(n.code) WHERE n.k='plasmid'
  UNION ALL
  SELECT 'fish', f2.id, n.alias, n.k, n.code
  FROM norm n JOIN public.fish f2 ON lower(f2.fish_code)=lower(n.code) WHERE n.k='fish'
  UNION ALL
  SELECT 'tank', tk.id, n.alias, n.k, n.code
  FROM norm n JOIN public.tanks tk ON lower(tk.tank_code)=lower(n.code) WHERE n.k='tank'
  UNION ALL
  SELECT 'cross', cr.id, n.alias, n.k, n.code
  FROM norm n JOIN public.crosses cr ON lower(COALESCE(cr.cross_run_code,''))=lower(n.code) WHERE n.k='cross'
  UNION ALL
  SELECT 'clutch_inst', ci.id, n.alias, n.k, n.code
  FROM norm n JOIN public.clutch_instances ci ON lower(COALESCE(ci.clutch_instance_code,''))=lower(n.code) WHERE n.k='clutch_inst'
  UNION ALL
  SELECT 'treated_clutch', tc.id, n.alias, n.k, n.code
  FROM norm n JOIN public.treated_clutches tc ON lower(COALESCE(tc.treated_clutch_code,''))=lower(n.code) WHERE n.k='treated_clutch'
),
ins AS (
  INSERT INTO public.join_aliases(target_kind, target_id, alias)
  SELECT kind, target_id, alias FROM res
  ON CONFLICT (target_kind, target_id, alias_norm) DO NOTHING
  RETURNING 1
),
unk AS (
  SELECT n.k AS target_kind, n.code AS target_code, n.alias
  FROM norm n
  LEFT JOIN res r ON r.k=n.k AND r.code=n.code AND r.alias=n.alias
  WHERE r.target_id IS NULL
)
SELECT
  (SELECT COUNT(*) FROM ins) AS inserted_count,
  (SELECT COALESCE(json_agg(unk.*), '[]'::json) FROM unk) AS unknown_json;
"""

with _eng().begin() as cx:
    cx.execute(text(sql_stage))
    for k, c, a in df[["target_kind","target_code","alias"]].itertuples(index=False):
        cx.execute(text(sql_copy_values), {"k": k, "c": c, "a": a})
    rec = cx.execute(text(sql_insert)).mappings().first()
    inserted = int(rec["inserted_count"])
    unknown_json = rec["unknown_json"]

st.success(f"Aliases inserted: {inserted}")

if unknown_json and unknown_json != []:
    try:
        unk_df = pd.read_json(io.StringIO(pd.Series([unknown_json]).to_json(orient="records"))).explode(0).reset_index(drop=True)
        # Fallback: direct normalize
    except Exception:
        unk_df = pd.json_normalize(unknown_json)
    if not isinstance(unknown_json, list):
        unk_df = pd.json_normalize(unknown_json)
    st.warning("Some codes were not found in the target tables. Fix target_code or load those entities first.")
    st.dataframe(pd.DataFrame(unknown_json), use_container_width=True, hide_index=True)
    st.download_button(
        "⬇︎ Download unknown codes",
        data=pd.DataFrame(unknown_json).to_csv(index=False).encode("utf-8"),
        file_name="aliases_unknown_codes.csv",
        use_container_width=True,
    )