# supabase/ui/pages/09_seed_loader.py
import io, zipfile, re, math
from datetime import datetime
from typing import Optional, List

import pandas as pd
import streamlit as st
from sqlalchemy import text

# minimal dependency: your engine builder that reads st.secrets PG*
# pages/*.py
from lib.db import get_engine
from lib.authz import require_app_access
require_app_access("🔐 CARP — Private")
engine = get_engine()

st.set_page_config(page_title="Seed Loader (ZIP-only, strict fish_name)", layout="wide")
st.title("Seed Loader — ZIP only (strict fish_name)")

st.caption("""
Upload a single **ZIP** of a seed kit folder. Expected files (case-insensitive):
- **02_transgenes.csv** — catalog: `transgene_base_code, name, description`
- **03_transgene_alleles.csv** — alleles: `transgene_base_code, allele_number, allele_name, description`
- **01_fish.csv** — fish rows (**must contain** `fish_name`; optional: `nickname, date_of_birth, line_building_stage, strain, description, batch_label`)
- **10_fish_transgene_alleles.csv** — links: `fish_name, transgene_base_code, allele_number, zygosity`

Load order is **02 → 03 → 01 → 10**. Missing files are skipped.
**Strict mode:** CSV **must** have `fish_name` (and **must not** use `name`) for fish and link rows.
""")

# ---------------- engine ----------------
engine = get_engine()

# ---------------- tiny helpers ----------------
def _has_rows(df) -> bool:
    """True iff df is a non-empty DataFrame."""
    return isinstance(df, pd.DataFrame) and not df.empty

def _require_fish_name_only(df, filename: str):
    if df is None:
        return
    cols = [c.strip().lower() for c in df.columns]
    if "fish_name" not in cols:
        raise ValueError(f"{filename} must include a 'fish_name' column (strict mode).")
    if "name" in cols:
        raise ValueError(f"{filename} must NOT include a 'name' column. Use only 'fish_name'.")
    # Normalize header case to be safe
    df.columns = cols

def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.where(pd.notna(df), None)
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: None if v is None else str(v).strip())
    return df

def _blank(x) -> str:
    if x is None: return ""
    if isinstance(x, float):
        try:
            if math.isnan(x):
                return ""
        except Exception:
            pass
    s = str(x).strip()
    return "" if s.lower() == "nan" else s

def _none_if_blank(x):
    s = _blank(x)
    return None if s == "" else s

def _parse_date(x):
    if x is None: return None
    s = str(x).strip()
    if not s or s.lower() == "nan": return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def _derive_batch_id_from_zip(name: str) -> str:
    # Use the full zip stem (e.g., 2025-09-22-2205-seedkit_transgene_alleles_dqm)
    return re.sub(r"\.zip$", "", name, flags=re.IGNORECASE)

def _exec(cx, sql: str, params: Optional[dict] = None):
    cx.execute(text(sql), params or {})

def _fetch_df(sql: str, params: Optional[dict] = None) -> pd.DataFrame:
    with engine.connect() as cx:
        return pd.read_sql(text(sql), cx, params=params or {})

# ---- DB bootstrap helpers (idempotent) ----
def _ensure_auto_fish_helpers(cx):
    _exec(cx, "CREATE SEQUENCE IF NOT EXISTS public.auto_fish_seq;")
    _exec(cx, """
    CREATE OR REPLACE FUNCTION public.next_auto_fish_code()
    RETURNS text LANGUAGE sql AS $$
      SELECT 'FSH-' || to_char(now(), 'YYYY') || '-' ||
             to_char(nextval('public.auto_fish_seq'), 'FM000')
    $$;
    """)

def _ensure_tank_helpers(cx):
    _exec(cx, "CREATE SEQUENCE IF NOT EXISTS public.tank_label_seq;")
    # IMPORTANT: keep arg name EXACTLY "prefix" to avoid the rename error
    _exec(cx, """
    CREATE OR REPLACE FUNCTION public.next_tank_code(prefix text)
    RETURNS text LANGUAGE plpgsql AS $func$
    DECLARE n bigint;
    BEGIN
      n := nextval('public.tank_label_seq');
      RETURN prefix || to_char(n, 'FM000');
    END
    $func$;
    """)

def _ensure_allele_table(cx):
    _exec(cx, """
    CREATE TABLE IF NOT EXISTS public.transgene_alleles(
      transgene_base_code text NOT NULL,
      allele_number text NOT NULL,
      allele_name text,
      description text,
      PRIMARY KEY (transgene_base_code, allele_number)
    );
    """)

# ---- upserts / inserts ----
def _upsert_transgenes(cx, df_tg: pd.DataFrame):
    _exec(cx, "ALTER TABLE public.transgenes ADD COLUMN IF NOT EXISTS name text;")
    _exec(cx, "ALTER TABLE public.transgenes ADD COLUMN IF NOT EXISTS description text;")
    up = text("""
      INSERT INTO public.transgenes(transgene_base_code, name, description)
      VALUES (:tbc, :name, :desc)
      ON CONFLICT (transgene_base_code) DO UPDATE
        SET name = COALESCE(NULLIF(EXCLUDED.name,''), public.transgenes.name),
            description = COALESCE(NULLIF(EXCLUDED.description,''), public.transgenes.description)
    """)
    for r in df_tg.to_dict(orient="records"):
        cx.execute(up, {
            "tbc": _blank(r.get("transgene_base_code")),
            "name": _blank(r.get("name")),
            "desc": _blank(r.get("description")),
        })

def _upsert_alleles(cx, df_ac: pd.DataFrame):
    _ensure_allele_table(cx)
    up = text("""
      INSERT INTO public.transgene_alleles(transgene_base_code, allele_number, allele_name, description)
      VALUES (:tbc, :alle, :aname, :desc)
      ON CONFLICT (transgene_base_code, allele_number) DO UPDATE
        SET allele_name = COALESCE(NULLIF(EXCLUDED.allele_name,''), public.transgene_alleles.allele_name),
            description = COALESCE(NULLIF(EXCLUDED.description,''), public.transgene_alleles.description)
    """)
    for r in df_ac.to_dict(orient="records"):
        cx.execute(up, {
            "tbc": _blank(r.get("transgene_base_code")),
            "alle": _blank(r.get("allele_number")),
            "aname": _blank(r.get("allele_name")),
            "desc": _blank(r.get("description")),
        })

def _insert_fish_by_name(cx, df_fish: pd.DataFrame, default_batch: Optional[str]):
    # Strict: must have fish_name (normalize to name)
    if "fish_name" in df_fish.columns and "name" not in df_fish.columns:
        df_fish["name"] = df_fish["fish_name"]
    if "name" not in df_fish.columns:
        raise ValueError("01_fish.csv must include a 'fish_name' column (or 'name').")

    # Target columns
    for c in ["batch_label","line_building_stage","nickname","date_of_birth","description","strain"]:
        if c not in df_fish.columns: df_fish[c] = None

    # Apply defaults
    if default_batch:
        df_fish["batch_label"] = df_fish["batch_label"].apply(lambda v: default_batch if _blank(v)=="" else v)
    df_fish["date_of_birth"] = df_fish["date_of_birth"].apply(_parse_date)

    # Ensure columns exist
    _exec(cx, "ALTER TABLE public.fish ADD COLUMN IF NOT EXISTS batch_label text;")
    _exec(cx, "ALTER TABLE public.fish ADD COLUMN IF NOT EXISTS line_building_stage text;")
    _exec(cx, "ALTER TABLE public.fish ADD COLUMN IF NOT EXISTS nickname text;")
    _exec(cx, "ALTER TABLE public.fish ADD COLUMN IF NOT EXISTS description text;")
    _exec(cx, "ALTER TABLE public.fish ADD COLUMN IF NOT EXISTS strain text;")
    _exec(cx, "ALTER TABLE public.fish ADD COLUMN IF NOT EXISTS date_of_birth date;")
    _exec(cx, "ALTER TABLE public.fish ADD COLUMN IF NOT EXISTS auto_fish_code text;")

    # 1) UPDATE existing fish by name: only fill blanks/nulls (don't clobber real values)
    upd = text("""
        UPDATE public.fish AS f
        SET batch_label       = COALESCE(NULLIF(:batch_label,''), f.batch_label),
            line_building_stage = COALESCE(NULLIF(:line_building_stage,''), f.line_building_stage),
            nickname          = COALESCE(NULLIF(:nickname,''), f.nickname),
            date_of_birth     = COALESCE(:date_of_birth, f.date_of_birth),
            description       = COALESCE(NULLIF(:description,''), f.description),
            strain            = COALESCE(NULLIF(:strain,''), f.strain)
        WHERE f.name = :name
    """)

    # 2) INSERT if not present (generate auto fish code)
    ins = text("""
        INSERT INTO public.fish(
          name, fish_code, batch_label, line_building_stage, nickname, date_of_birth, description, strain, auto_fish_code
        )
        SELECT :name, NULL, :batch_label, :line_building_stage, :nickname, :date_of_birth, :description, :strain,
               public.next_auto_fish_code()
        WHERE NOT EXISTS (SELECT 1 FROM public.fish f WHERE f.name = :name)
    """)

    rows = df_fish[["name","batch_label","line_building_stage","nickname","date_of_birth","description","strain"]] \
           .to_dict(orient="records")

    for r in rows:
        params = {
            "name": _blank(r.get("name")),
            "batch_label": _blank(r.get("batch_label")),
            "line_building_stage": _blank(r.get("line_building_stage")),
            "nickname": _blank(r.get("nickname")),
            "date_of_birth": _none_if_blank(r.get("date_of_birth")),
            "description": _blank(r.get("description")),
            "strain": _blank(r.get("strain")),
        }
        cx.execute(upd, params)   # fill blanks on existing rows
        cx.execute(ins, params)   # insert if it wasn't there

def _ensure_transgenes_exist(cx, base_codes: List[str]):
    _exec(cx, "ALTER TABLE public.transgenes ADD COLUMN IF NOT EXISTS name text;")
    up = text("""
      INSERT INTO public.transgenes(transgene_base_code, name)
      VALUES (:tbc, :tbc)
      ON CONFLICT (transgene_base_code) DO NOTHING
    """)
    for tbc in base_codes:
        cx.execute(up, {"tbc": _blank(tbc)})

def _insert_links_by_fish_name(cx, df_links: pd.DataFrame):
    if "fish_name" not in df_links.columns:
        raise ValueError("10_fish_transgene_alleles.csv must include 'fish_name'.")
    for c in ["transgene_base_code","allele_number","zygosity"]:
        if c not in df_links.columns: df_links[c] = None

    sql = text("""
      INSERT INTO public.fish_transgene_alleles(fish_id, transgene_base_code, allele_number, zygosity)
      SELECT f.id, :tbc, nullif(:alle,''), nullif(:zyg,'')
      FROM public.fish f
      WHERE f.name = :fname
      ON CONFLICT DO NOTHING
    """)
    for r in df_links.to_dict(orient="records"):
        cx.execute(sql, {
            "fname": _blank(r.get("fish_name")),
            "tbc": _blank(r.get("transgene_base_code")),
            "alle": _blank(r.get("allele_number")),
            "zyg": _blank(r.get("zygosity")),
        })

# ---- PREVIEW (Overview-like) ----
def _build_preview(df_fish, df_links, df_tg, default_batch):
    if not _has_rows(df_fish):
        return pd.DataFrame()

    fish = df_fish.copy()

    # Normalize to a single canonical 'fish_name' column:
    # - Strict input allows only 'fish_name' (we already enforce earlier),
    #   but to be defensive we convert to 'name' then drop the original.
    if "fish_name" in fish.columns:
        fish["name"] = fish["fish_name"]
        fish = fish.drop(columns=["fish_name"])  # <-- prevents duplicate labels

    if "name" not in fish.columns:
        return pd.DataFrame()  # strict

    # Fill/normalize other columns
    if "batch_label" not in fish.columns:
        fish["batch_label"] = None
    fish["batch_label"] = fish["batch_label"].apply(
        lambda v: default_batch if (v is None or str(v).strip()=="") else v
    )
    if "date_of_birth" in fish.columns:
        fish["date_of_birth"] = fish["date_of_birth"].apply(_parse_date)
    else:
        fish["date_of_birth"] = None

    # Build the base select with a single 'fish_name' column
    base = fish.rename(columns={"name":"fish_name"})[[
        "fish_name","nickname","batch_label","line_building_stage","date_of_birth","strain","description"
    ]].copy()

    # Aggregate transgenes/alleles from links
    tg_df = pd.DataFrame(columns=["fish_name","transgenes"])
    alle_df = pd.DataFrame(columns=["fish_name","alleles"])

    if _has_rows(df_links):
        lnk = df_links.copy()
        for c in ["fish_name","transgene_base_code","allele_number","zygosity"]:
            if c not in lnk.columns: lnk[c] = None

        # Optional display names from 02
        disp = None
        if _has_rows(df_tg) and "name" in df_tg.columns:
            disp = df_tg[["transgene_base_code","name"]].copy()
            disp["disp_name"] = disp["name"].apply(
                lambda x: x.strip() if isinstance(x,str) and x.strip() else None
            )
            disp["disp_name"] = disp.apply(
                lambda r: r["disp_name"] if r["disp_name"] else r["transgene_base_code"],
                axis=1
            )

        l2 = lnk.copy()
        if disp is not None:
            l2 = l2.merge(disp[["transgene_base_code","disp_name"]], on="transgene_base_code", how="left")
            l2["tg_name"] = l2.apply(
                lambda r: r["disp_name"] if isinstance(r.get("disp_name"), str) and r["disp_name"].strip()
                else r.get("transgene_base_code"), axis=1
            )
        else:
            l2["tg_name"] = l2["transgene_base_code"]

        g_tg = (
            l2.dropna(subset=["fish_name"])
              .groupby("fish_name")["tg_name"]
              .apply(lambda s: ", ".join(sorted({x for x in s if isinstance(x,str) and x.strip()})))
        ).reset_index().rename(columns={"tg_name":"transgenes"})
        tg_df = g_tg

        def _alle_label(row):
            basec = row.get("transgene_base_code")
            ann   = row.get("allele_number")
            basec = basec if isinstance(basec,str) and basec.strip() else ""
            ann   = ann if isinstance(ann,str) and ann.strip() else ""
            return f"{basec}({ann})" if (basec and ann) else (basec or "")
        l2["alle_label"] = l2.apply(_alle_label, axis=1)

        g_alle = (
            l2.dropna(subset=["fish_name"])
              .groupby("fish_name")["alle_label"]
              .apply(lambda s: ", ".join(sorted({x for x in s if isinstance(x,str) and x.strip()})))
        ).reset_index().rename(columns={"alle_label":"alleles"})
        alle_df = g_alle

    prev = base.merge(tg_df, on="fish_name", how="left").merge(alle_df, on="fish_name", how="left")
    prev["transgenes"] = prev["transgenes"].fillna("")
    prev["alleles"] = prev["alleles"].fillna("")
    prev["auto_fish_code"] = "(to be generated)"
    prev["tank"] = ""

    # Final shape (and ensure uniqueness of labels defensively)
    prev = prev.loc[:, ~prev.columns.duplicated()]
    cols = [
        "fish_name","nickname","auto_fish_code","batch_label",
        "line_building_stage","date_of_birth","tank","transgenes","alleles","description"
    ]
    return prev[cols]

# ---------------- UI ----------------
zip_file = st.file_uploader("Upload seed kit ZIP", type=["zip"])
batch_override = st.text_input("Batch ID override (optional)", value="", placeholder="leave blank to use full zip filename")
assign_tanks_after = st.checkbox("Assign tanks after load", value=True)

df_02 = df_03 = df_01 = df_10 = None
derived_batch = ""

if zip_file:
    z = zipfile.ZipFile(io.BytesIO(zip_file.read()))
    names = [n for n in z.namelist() if not n.endswith("/")]

    def read_csv_like(patterns):
        for n in names:
            nl = n.lower()
            if any(p in nl for p in patterns):
                with z.open(n) as f:
                    return pd.read_csv(f)
        return None

    df_02 = read_csv_like(["02_transgenes.csv"])
    df_03 = read_csv_like(["03_transgene_alleles.csv"])
    df_01 = read_csv_like(["01_fish.csv"])
    df_10 = read_csv_like(["10_fish_transgene_alleles.csv"])

    if _has_rows(df_02): df_02 = _clean_df(df_02)
    if _has_rows(df_03): df_03 = _clean_df(df_03)
    if _has_rows(df_01): df_01 = _clean_df(df_01)
    if _has_rows(df_10): df_10 = _clean_df(df_10)

    # Strict: fish & links must have fish_name (and NOT 'name')
    if df_01 is not None: _require_fish_name_only(df_01, "01_fish.csv")
    if df_10 is not None: _require_fish_name_only(df_10, "10_fish_transgene_alleles.csv")

    derived_batch = batch_override.strip() or _derive_batch_id_from_zip(zip_file.name)
    st.success(f"Derived batch_id → **{derived_batch}** (this will be written to `fish.batch_label`)")

    st.caption(
        f"loaded → 02:{_has_rows(df_02)} · 03:{_has_rows(df_03)} · 01:{_has_rows(df_01)} · 10:{_has_rows(df_10)}"
    )

    st.write("**Detected files:**")
    st.json({
        "02_transgenes.csv": (len(df_02) if _has_rows(df_02) else 0),
        "03_transgene_alleles.csv": (len(df_03) if _has_rows(df_03) else 0),
        "01_fish.csv": (len(df_01) if _has_rows(df_01) else 0),
        "10_fish_transgene_alleles.csv": (len(df_10) if _has_rows(df_10) else 0),
    })

    # Preview
    if st.button("Build preview (no DB writes)"):
        try:
            prev = _build_preview(df_01, df_10, df_02, derived_batch)
            if prev.empty:
                st.warning("Nothing to preview (need 01_fish.csv with fish_name).")
            else:
                st.dataframe(prev, hide_index=True, use_container_width=True)
                st.download_button(
                    "Download preview CSV",
                    prev.to_csv(index=False).encode("utf-8"),
                    file_name="seed_preview.csv",
                    mime="text/csv"
                )
        except Exception as e:
            st.error(f"Preview failed: {e}")

    # Load
    if st.button("Load seed kit from ZIP"):
        try:
            with engine.begin() as cx:
                _ensure_auto_fish_helpers(cx)

                # 02 — transgenes
                if _has_rows(df_02):
                    for c in ["transgene_base_code","name","description"]:
                        if c not in df_02.columns: df_02[c] = None
                    _upsert_transgenes(cx, df_02)

                # 03 — alleles
                if _has_rows(df_03):
                    for c in ["transgene_base_code","allele_number","allele_name","description"]:
                        if c not in df_03.columns: df_03[c] = None
                    _upsert_alleles(cx, df_03)

                # 01 — fish (force blank batches to derived batch)
                if _has_rows(df_01):
                    if "batch_label" not in df_01.columns:
                        df_01["batch_label"] = None
                    df_01["batch_label"] = df_01["batch_label"].apply(
                        lambda v: derived_batch if _blank(v)=="" else v
                    )
                    _insert_fish_by_name(cx, df_01, default_batch=derived_batch)

                # 10 — links (ensure transgenes exist first)
                if _has_rows(df_10):
                    for c in ["transgene_base_code","allele_number","zygosity","fish_name"]:
                        if c not in df_10.columns: df_10[c] = None
                    base_codes = sorted(df_10["transgene_base_code"].dropna().unique().tolist())
                    _ensure_transgenes_exist(cx, base_codes)
                    _insert_links_by_fish_name(cx, df_10)

                # Tanks (optional)
                if assign_tanks_after:
                    _ensure_tank_helpers(cx)
                    _exec(cx, """
                        INSERT INTO public.tank_assignments(fish_id, tank_label, status)
                        SELECT f.id, public.next_tank_code('TANK-'), 'inactive'
                        FROM public.fish f
                        LEFT JOIN public.tank_assignments ta ON ta.fish_id = f.id
                        WHERE ta.fish_id IS NULL
                    """)

            st.success("Seed kit loaded ✅")
            st.toast("All done", icon="🎉")

            # -------- Post-insert sanity snapshot (what the UI shows) --------
            st.subheader("Post-insert sanity check")
            counts = _fetch_df("""
              SELECT
                (SELECT count(*) FROM public.fish WHERE batch_label=:b) AS n_fish,
                (SELECT count(*) FROM public.fish f
                   JOIN public.fish_transgene_alleles l ON l.fish_id=f.id
                 WHERE f.batch_label=:b) AS n_links
            """, {"b": derived_batch})
            st.dataframe(counts, hide_index=True, use_container_width=True)

            sample = _fetch_df("""
              SELECT fish_name, auto_fish_code, transgenes, alleles
              FROM public.v_fish_overview_v1
              WHERE batch = :b
              ORDER BY fish_name
              LIMIT 50
            """, {"b": derived_batch})
            if sample.empty:
                st.warning("No rows found in overview for this batch (unexpected).")
            else:
                st.dataframe(sample, hide_index=True, use_container_width=True)

        except Exception as e:
            st.error(f"ZIP load failed: {e}")
else:
    st.info("Upload a ZIP to begin.")