import io, zipfile, re, math
from datetime import datetime
from typing import Optional, List

import pandas as pd
import streamlit as st
from sqlalchemy import text

from lib_shared import pick_environment
from lib.db import get_engine, fetch_df, exec_sql

st.set_page_config(page_title="Seed Loader (ZIP only)", layout="wide")
st.title("Seed Loader — ZIP only (strict fish_name)")

st.caption("""
Upload a **single ZIP** of a seed kit folder. Expected files (case-insensitive names):
- **02_transgenes.csv** — transgene catalog (transgene_base_code, name, description)
- **03_transgene_alleles.csv** — allele catalog (transgene_base_code, allele_number, allele_name, description)
- **01_fish.csv** — fish rows (**fish_name** required; optional: nickname, date_of_birth, line_building_stage, strain, description, batch_label)
- **10_fish_transgene_alleles.csv** — links fish_name ↔ (transgene_base_code, allele_number, zygosity)

Load order is **02 → 03 → 01 → 10**. Missing files are skipped.

**Strict mode:** Humans provide `fish_name` only; `auto_fish_code` is always generated.
""")

# -------- env / engine ----------
env, conn = pick_environment()
engine = get_engine(conn)
st.info(f"Environment: **{env}**")

# -------- helpers ----------
def _derive_batch_id(name: str) -> str:
    m = re.search(r"\d{4}-\d{2}-\d{2}-\d{4}", name)
    base = m.group(0) if m else re.sub(r"\.zip$", "", name).split("/")[-1]
    return base

def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase headers, trim strings, keep None for blanks/NaN."""
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.where(pd.notna(df), None)
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: None if v is None else str(v).strip())
    return df

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

def _blank(x) -> str:
    """Return '' for None/NaN/blank; else trimmed string."""
    if x is None:
        return ""
    if isinstance(x, float):
        try:
            if math.isnan(x):
                return ""
        except Exception:
            pass
    s = str(x).strip()
    return "" if s.lower() == "nan" else s

def _none_if_blank(x):
    """Return None for None/NaN/blank; else trimmed string."""
    s = _blank(x)
    return None if s == "" else s

def _ensure_tank_helpers(cx):
    exec_sql(cx, "create sequence if not exists public.tank_label_seq")
    exec_sql(cx, """
    create or replace function public.next_tank_code(p_prefix text)
    returns text language plpgsql as $func$
    declare n bigint;
    begin
      n := nextval('public.tank_label_seq');
      return p_prefix || to_char(n, 'FM000');
    end
    $func$;
    """)

def _ensure_auto_fish_helpers(cx):
    exec_sql(cx, "create sequence if not exists public.auto_fish_seq")
    exec_sql(cx, """
    create or replace function public.next_auto_fish_code()
    returns text language sql as $$
      select
        'FSH-' || to_char(now(), 'YYYY') || '-' ||
        to_char(nextval('public.auto_fish_seq'), 'FM000')
    $$;
    """)

def _upsert_transgenes(cx, df_tg: pd.DataFrame):
    exec_sql(cx, "alter table public.transgenes add column if not exists name text")
    exec_sql(cx, "alter table public.transgenes add column if not exists description text")
    upsert = text("""
        insert into public.transgenes(transgene_base_code, name, description)
        values (:tbc, :name, :desc)
        on conflict (transgene_base_code) do update
          set name = coalesce(nullif(excluded.name, ''), public.transgenes.name),
              description = coalesce(nullif(excluded.description, ''), public.transgenes.description)
    """)
    for r in df_tg.to_dict(orient="records"):
        cx.execute(upsert, {
            "tbc": _blank(r.get("transgene_base_code")),
            "name": _blank(r.get("name")),
            "desc": _blank(r.get("description")),
        })

def _upsert_allele_catalog(cx, df_ac: pd.DataFrame):
    exec_sql(cx, """
        create table if not exists public.transgene_allele_catalog(
          transgene_base_code text not null,
          allele_number text not null,
          allele_name text,
          description text,
          primary key (transgene_base_code, allele_number)
        )
    """)
    upsert = text("""
        insert into public.transgene_allele_catalog(transgene_base_code, allele_number, allele_name, description)
        values (:tbc, :alle, :aname, :desc)
        on conflict (transgene_base_code, allele_number) do update
          set allele_name = coalesce(nullif(excluded.allele_name,''), public.transgene_allele_catalog.allele_name),
              description = coalesce(nullif(excluded.description,''), public.transgene_allele_catalog.description)
    """)
    for r in df_ac.to_dict(orient="records"):
        cx.execute(upsert, {
            "tbc": _blank(r.get("transgene_base_code")),
            "alle": _blank(r.get("allele_number")),
            "aname": _blank(r.get("allele_name")),
            "desc": _blank(r.get("description")),
        })

def _insert_fish(cx, df_fish: pd.DataFrame, default_batch: Optional[str]):
    # Required headers: fish_name (or name)
    # Optional: nickname, date_of_birth, line_building_stage, strain, description, batch_label
    cols = ["name","batch_label","line_building_stage","nickname","date_of_birth","description","strain"]
    for c in cols:
        if c not in df_fish.columns:
            df_fish[c] = None

    # Strict: enforce name present (fish_name normalized to name before call)
    if not df_fish["name"].notna().any():
        raise ValueError("01_fish.csv must include a 'fish_name' column (or 'name').")

    # Fill defaults
    if default_batch:
        df_fish["batch_label"] = df_fish["batch_label"].apply(
            lambda v: default_batch if _blank(v) == "" else v
        )
    df_fish["date_of_birth"] = df_fish["date_of_birth"].apply(_parse_date)

    # Defensive columns on table
    exec_sql(cx, "alter table public.fish add column if not exists batch_label text")
    exec_sql(cx, "alter table public.fish add column if not exists line_building_stage text")
    exec_sql(cx, "alter table public.fish add column if not exists nickname text")
    exec_sql(cx, "alter table public.fish add column if not exists description text")
    exec_sql(cx, "alter table public.fish add column if not exists strain text")
    exec_sql(cx, "alter table public.fish add column if not exists date_of_birth date")
    exec_sql(cx, "alter table public.fish add column if not exists auto_fish_code text")

    # Always generate compliant auto_fish_code; key by name (prevent duplicates by name)
    ins = text("""
        insert into public.fish(
            name, fish_code, batch_label, line_building_stage, nickname, date_of_birth, description, strain, auto_fish_code
        )
        select :name, NULL, :batch_label, :line_building_stage, :nickname, :date_of_birth, :description, :strain,
               public.next_auto_fish_code()
        where not exists (select 1 from public.fish f where f.name = :name)
    """)

    for r in df_fish[cols].to_dict(orient="records"):
        cx.execute(ins, {
            "name": _blank(r.get("name")),
            "batch_label": _blank(r.get("batch_label")),
            "line_building_stage": _blank(r.get("line_building_stage")),
            "nickname": _blank(r.get("nickname")),
            "date_of_birth": _none_if_blank(r.get("date_of_birth")),
            "description": _blank(r.get("description")),
            "strain": _blank(r.get("strain")),
        })

def _ensure_transgenes_exist(cx, base_codes: List[str]):
    exec_sql(cx, "alter table public.transgenes add column if not exists name text")
    upsert_t = text("""
        insert into public.transgenes(transgene_base_code, name)
        values (:tbc, :tbc)
        on conflict (transgene_base_code) do nothing
    """)
    for tbc in base_codes:
        cx.execute(upsert_t, {"tbc": _blank(tbc)})

def _insert_links_by_name(cx, df_links: pd.DataFrame):
    # Strict: must have fish_name
    if "fish_name" not in df_links.columns:
        raise ValueError("10_fish_transgene_alleles.csv must include a 'fish_name' column.")
    sql = """
        insert into public.fish_transgene_alleles(fish_id, transgene_base_code, allele_number, zygosity)
        select f.id, :tbc, nullif(:alle,''), nullif(:zyg,'')
        from public.fish f
        where f.name = :fname
        on conflict do nothing
    """
    ins = text(sql)
    for r in df_links.to_dict(orient="records"):
        cx.execute(ins, {
            "fname": _blank(r.get("fish_name")),
            "tbc": _blank(r.get("transgene_base_code")),
            "alle": _blank(r.get("allele_number")),
            "zyg": _blank(r.get("zygosity")),
        })

# -------- ZIP input ----------
zip_file = st.file_uploader("Upload **seed kit ZIP** (drag the folder as .zip)", type=["zip"])
batch_override = st.text_input("Batch ID override (optional)", value="", placeholder="e.g., 2025-09-22-2205 or BATCH-001")
assign_tanks_after = st.checkbox("Assign tanks after load", value=True)

if zip_file:
    z = zipfile.ZipFile(io.BytesIO(zip_file.read()))
    names = [n for n in z.namelist() if not n.endswith("/")]  # files only

    def read_csv_like(patterns):
        for n in names:
            nl = n.lower()
            if any(p in nl for p in patterns):
                with z.open(n) as f:
                    return pd.read_csv(f)   # raw df
        return None

    # Build & clean dataframes
    df_02 = read_csv_like(["02_transgenes.csv"])
    df_03 = read_csv_like(["03_transgene_alleles.csv"])
    df_01 = read_csv_like(["01_fish.csv"])
    df_10 = read_csv_like(["10_fish_transgene_alleles.csv"])

    if df_02 is not None: df_02 = _clean_df(df_02)
    if df_03 is not None: df_03 = _clean_df(df_03)
    if df_01 is not None: df_01 = _clean_df(df_01)
    if df_10 is not None:
        df_10 = _clean_df(df_10)
        # Normalize allele header and coerce values to clean strings (e.g., 201.0 -> 201)
        if "allele" in df_10.columns and "allele_number" not in df_10.columns:
            df_10["allele_number"] = df_10["allele"]
            df_10 = df_10.drop(columns=["allele"])
        if "allele_number" in df_10.columns:
            import re as _re
            def _clean_alle(v):
                s = _blank(v)
                if s == "":
                    return None
                return _re.sub(r"\.0$", "", s)  # drop trailing .0
            df_10["allele_number"] = df_10["allele_number"].map(_clean_alle)

    # Normalize headers for fish: collapse to a single 'name' column (avoid duplicate labels)
    if df_01 is not None:
        if "fish_name" in df_01.columns:
            if "name" in df_01.columns:
                df_01["name"] = df_01["name"].where(
                    df_01["name"].notna() & (df_01["name"].astype(str).str.strip() != ""),
                    df_01["fish_name"]
                )
            else:
                df_01["name"] = df_01["fish_name"]
            df_01 = df_01.drop(columns=["fish_name"])
        if "name" not in df_01.columns:
            st.error("01_fish.csv must include a 'fish_name' column (or 'name').")
            df_01 = None  # stop early

    # Strict for links: must have fish_name
    if df_10 is not None and "fish_name" not in df_10.columns:
        st.error("10_fish_transgene_alleles.csv must include a 'fish_name' column.")
        df_10 = None

    st.write("**Detected files:**")
    st.json({
        "02_transgenes.csv": (len(df_02) if df_02 is not None else 0),
        "03_transgene_alleles.csv": (len(df_03) if df_03 is not None else 0),
        "01_fish.csv": (len(df_01) if df_01 is not None else 0),
        "10_fish_transgene_alleles.csv": (len(df_10) if df_10 is not None else 0),
    })

    suggested_batch = (batch_override.strip() or _derive_batch_id(zip_file.name))
    st.write(f"Derived batch id: **{suggested_batch}** (applied to fish with blank `batch_label`)")

    # --- PREVIEW -------------------------------------------------------------
    def _build_preview(df_01, df_10, df_02, df_03, default_batch):
        if df_01 is None or df_01.empty:
            return pd.DataFrame()

        fish = df_01.copy()

        # Safety: collapse fish_name/name to a single 'name' column to avoid duplicate labels
        if "fish_name" in fish.columns:
            if "name" in fish.columns:
                fish["name"] = fish["name"].where(
                    fish["name"].notna() & (fish["name"].astype(str).str.strip() != ""),
                    fish["fish_name"]
                )
            else:
                fish["name"] = fish["fish_name"]
            fish = fish.drop(columns=["fish_name"])

        if "batch_label" not in fish.columns:
            fish["batch_label"] = None
        fish["batch_label"] = fish["batch_label"].apply(
            lambda v: default_batch if (v is None or str(v).strip() == "") else v
        )
        if "date_of_birth" in fish.columns:
            fish["date_of_birth"] = fish["date_of_birth"].apply(_parse_date)
        else:
            fish["date_of_birth"] = None

        fish_base = fish.rename(columns={"name": "fish_name"})[[
            "fish_name", "nickname", "batch_label",
            "line_building_stage", "date_of_birth", "strain", "description"
        ]].copy()

        tg_df = pd.DataFrame(columns=["fish_name","transgenes"])
        alle_df = pd.DataFrame(columns=["fish_name","alleles"])
        alle_num_df = pd.DataFrame(columns=["fish_name","allele_numbers"])

        if df_10 is not None and not df_10.empty:
            links = df_10.copy()

            # Optional transgene display names from 02 (fall back to base code)
            if df_02 is not None and not df_02.empty and "name" in df_02.columns:
                disp = df_02[["transgene_base_code","name"]].copy()
                disp["disp_name"] = disp["name"].apply(
                    lambda x: x.strip() if isinstance(x,str) and x.strip() else None
                )
                disp["disp_name"] = disp.apply(
                    lambda r: r["disp_name"] if r["disp_name"] else r["transgene_base_code"],
                    axis=1
                )
            else:
                disp = None

            l2 = links.copy()
            for c in ["fish_name","transgene_base_code","allele_number","zygosity"]:
                if c not in l2.columns: l2[c] = None

            if disp is not None:
                l2 = l2.merge(disp[["transgene_base_code","disp_name"]],
                              on="transgene_base_code", how="left")
                l2["tg_name"] = l2.apply(
                    lambda r: r["disp_name"] if isinstance(r.get("disp_name"), str) and r["disp_name"].strip()
                    else r.get("transgene_base_code"), axis=1
                )
            else:
                l2["tg_name"] = l2["transgene_base_code"]

            # Transgene names
            g_tg = (
                l2.dropna(subset=["fish_name"])
                  .groupby("fish_name")["tg_name"]
                  .apply(lambda s: ", ".join(sorted({x for x in s if isinstance(x,str) and x.strip()})))
            )
            tg_df = g_tg.reset_index().rename(columns={"tg_name":"transgenes"})

            # Allele labels like base(allele)
            def _alle_label(row):
                base = row.get("transgene_base_code")
                ann  = row.get("allele_number")
                base = base if isinstance(base,str) and base.strip() else ""
                ann  = ann if isinstance(ann,str) and ann.strip() else ""
                return f"{base}({ann})" if (base and ann) else (base or "")

            l2["alle_label"] = l2.apply(_alle_label, axis=1)
            g_alle = (
                l2.dropna(subset=["fish_name"])
                  .groupby("fish_name")["alle_label"]
                  .apply(lambda s: ", ".join(sorted({x for x in s if isinstance(x,str) and x.strip()})))
            )
            alle_df = g_alle.reset_index().rename(columns={"alle_label":"alleles"})

            # NEW: raw allele_numbers list
            if "allele_number" in l2.columns:
                g_alle_nums = (
                    l2.dropna(subset=["fish_name"])
                      .groupby("fish_name")["allele_number"]
                      .apply(lambda s: ", ".join(sorted({x for x in s if isinstance(x,str) and x.strip()})))
                )
                alle_num_df = g_alle_nums.reset_index().rename(columns={"allele_number":"allele_numbers"})

        prev = (fish_base
                .merge(tg_df, on="fish_name", how="left")
                .merge(alle_df, on="fish_name", how="left")
                .merge(alle_num_df, on="fish_name", how="left"))
        prev["transgenes"] = prev["transgenes"].fillna("")
        prev["alleles"] = prev["alleles"].fillna("")
        prev["allele_numbers"] = prev.get("allele_numbers", "").fillna("")
        prev["auto_fish_code"] = "(to be generated)"
        prev["tank"] = ""  # assigned after load if checkbox checked

        cols = [
            "fish_name","nickname","auto_fish_code","batch_label",
            "line_building_stage","date_of_birth","tank",
            "transgenes","alleles","allele_numbers","description"
        ]
        prev = prev[cols]

        with engine.connect() as cx:
            existing = fetch_df(cx, "select name from public.fish")
        existing_names = set(existing["name"].tolist()) if not existing.empty else set()
        prev["status"] = prev["fish_name"].apply(lambda n: "exists" if n in existing_names else "new")

        return prev

    st.divider()
    st.subheader("Preview (no DB writes)")

    if st.button("Build preview"):
        try:
            preview_df = _build_preview(df_01, df_10, df_02, df_03, suggested_batch)
            if preview_df.empty:
                st.warning("Nothing to preview. Make sure 01_fish.csv is present.")
            else:
                st.success("Preview ready")
                st.dataframe(preview_df, hide_index=True, use_container_width=True)
                st.download_button(
                    "Download preview CSV",
                    preview_df.to_csv(index=False).encode("utf-8"),
                    file_name="seed_preview.csv",
                    mime="text/csv"
                )
                st.caption("Note: `auto_fish_code` is generated on insert; `tank` is added if “Assign tanks after load” is checked.")
        except Exception as e:
            st.error(f"Preview failed: {e}")

    # --- LOAD BUTTON ---------------------------------------------------------
    if st.button("Load seed kit from ZIP"):
        try:
            with engine.begin() as cx:
                _ensure_auto_fish_helpers(cx)

                if df_02 is not None and not df_02.empty:
                    for c in ["transgene_base_code","name","description"]:
                        if c not in df_02.columns: df_02[c] = None
                    _upsert_transgenes(cx, df_02)

                if df_03 is not None and not df_03.empty:
                    for c in ["transgene_base_code","allele_number","allele_name","description"]:
                        if c not in df_03.columns: df_03[c] = None
                    _upsert_allele_catalog(cx, df_03)

                if df_01 is not None and not df_01.empty:
                    if "batch_label" not in df_01.columns:
                        df_01["batch_label"] = None
                    _insert_fish(cx, df_01, default_batch=suggested_batch)

                if df_10 is not None and not df_10.empty:
                    for c in ["transgene_base_code","allele_number","zygosity","fish_name"]:
                        if c not in df_10.columns: df_10[c] = None
                    base_codes = sorted(df_10["transgene_base_code"].dropna().unique().tolist())
                    _ensure_transgenes_exist(cx, base_codes)
                    _insert_links_by_name(cx, df_10)

                if assign_tanks_after:
                    _ensure_tank_helpers(cx)
                    exec_sql(cx, """
                        insert into public.tank_assignments(fish_id, tank_label, status)
                        select f.id, public.next_tank_code('TANK-'), 'inactive'
                        from public.fish f
                        left join public.tank_assignments ta on ta.fish_id = f.id
                        where ta.fish_id is null
                    """)

            st.success("Seed kit loaded from ZIP.")
            st.toast("All done ✅", icon="🎉")
        except Exception as e:
            st.error(f"ZIP load failed: {e}")