# supabase/ui/pages/03_🐟_Wide_Upload.py
from __future__ import annotations

import os as _os
_os.environ.setdefault('PSYCOPG_FORCE_SIMPLE', '1')

import io
import re
import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# NOTE: we only need get_conn here; drop get_engine/fetch_df imports to avoid ImportError
from lib.db import get_conn  # psycopg3/2 connection factory

# ---------- Paths to SQL files ----------
PAGE_DIR = Path(__file__).parent
SQL_DIR = (PAGE_DIR.parent / "lib" / "seedloader").resolve()  # ../lib/seedloader
VALIDATE = SQL_DIR / "validate_wide.sql"
LOAD     = SQL_DIR / "load_wide.sql"

st.title("🐟 Wide Upload (ZIP or CSV) — no crosswalk")

# --- bootstrap: ensure raw schema/table exist (idempotent) ---
def _bootstrap_raw():
    ddl = """
    create schema if not exists raw;

    create table if not exists raw.wide_fish_upload(
      seed_batch_id        text not null,
      fish_name            text not null,
      nickname             text,
      birth_date           date,
      background_strain    text,
      strain               text,
      batch_label          text,
      line_building_stage  text,
      description          text,
      notes                text,
      transgene_base_code  text,
      allele_number        integer,
      allele_label_legacy  text,
      zygosity             text,
      created_by           text,
      created_at           timestamptz default now()
    );
    """
    with get_conn() as conn, conn.cursor() as cur:
        for _stmt in (s.strip() for s in ddl.split(';') if s.strip()):
            cur.execute(_stmt)

def _bootstrap_public_dicts():
    ddl = """
    create table if not exists public.transgenes(
      transgene_base_code text primary key
    );

    create table if not exists public.transgene_alleles(
      transgene_base_code text not null references public.transgenes(transgene_base_code),
      allele_number       integer not null,
      primary key (transgene_base_code, allele_number)
    );
    """
    with get_conn() as conn, conn.cursor() as cur:
        for _stmt in (s.strip() for s in ddl.split(';') if s.strip()):
            cur.execute(_stmt)

_bootstrap_raw()
_bootstrap_public_dicts()


if not VALIDATE.exists() or not LOAD.exists():
    st.error(f"Missing SQL files under {SQL_DIR}.\nExpected: {VALIDATE.name}, {LOAD.name}")
    st.stop()

# ---------- Expected CSV headers (strict; ordered for COPY) ----------
# We dropped allele_crosswalk entirely. Allele label legacy is optional and ignored by default.
REQUIRED_ORDER = [
    "seed_batch_id", "fish_name", "nickname", "birth_date",
    "background_strain", "strain", "batch_label", "line_building_stage",
    "description", "notes", "transgene_base_code", "allele_number",
    # kept in table but we’re not requiring/using it:
    # "allele_label_legacy",
    "zygosity", "created_by",
]

HELP = st.expander("ZIP/CSV format help", expanded=False)
HELP.write(
    """
- Upload **one ZIP** (preferred) that contains **exactly one** fish CSV, **or** upload a single CSV directly.
- `seed_batch_id` is **inferred from the uploaded filename** (ZIP or CSV). Humans **do not** type it.
- The uploader **normalizes** your CSV: adds any missing required columns, drops extras, orders columns for COPY,
  and formats `birth_date` to `YYYY-MM-DD`. Empty cells become SQL `NULL`.
- **Required columns we keep** (others are ignored):  
  `fish_name, nickname, birth_date, background_strain, strain, batch_label, line_building_stage, description, notes, transgene_base_code, allele_number, zygosity, created_by`.
"""
)

# ---------- File input ----------
uploaded = st.file_uploader("Upload a ZIP (preferred) or a single CSV", type=["zip", "csv"])

def infer_batch_from_filename(name: Optional[str]) -> str:
    """seed_kit_wide-2025-09-28.zip -> seed_kit_wide_2025_09_28"""
    if not name:
        return "seed_YYYY_MM_DD"
    stem = Path(name).stem
    stem = re.sub(r"[^0-9A-Za-z]+", "_", stem).strip("_").lower()
    if not stem.startswith("seed_"):
        stem = f"seed_{stem}"
    return stem

# ---------- CSV / ZIP extraction ----------
def _extract_csv_from_zip(file_bytes: bytes) -> tuple[str, bytes]:
    """
    Return (inner_filename, inner_csv_bytes).

    - Ignores macOS junk: __MACOSX/, entries starting with "._", and directories.
    - Looks for CSVs whose header includes 'fish_name' (case-insensitive).
    - If multiple candidates, pick the one with the most expected columns present.
      If still tied, pick the largest file.
    """
    def _is_junk(name: str) -> bool:
        base = name.split("/")[-1]
        return (
            name.endswith("/") or
            name.startswith("__MACOSX/") or
            base.startswith("._") or
            not name.lower().endswith(".csv")
        )

    import csv

    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        names = [n for n in zf.namelist() if not _is_junk(n)]

        # Collect candidates with simple header sniff
        candidates = []
        for n in names:
            try:
                with zf.open(n, "r") as f:
                    head = f.read(8192)
                # Try to decode; fall back to latin-1 if needed
                try:
                    text = head.decode("utf-8", errors="ignore")
                except Exception:
                    text = head.decode("latin-1", errors="ignore")
                # Parse just the first line as CSV
                first_line = text.splitlines()[0] if text else ""
                header = next(csv.reader([first_line])) if first_line else []
                header_lower = [h.strip().lower() for h in header]

                if "fish_name" in header_lower:
                    # Score by number of expected columns present
                    expected = {
                        "seed_batch_id", "fish_name", "nickname", "birth_date",
                        "background_strain", "strain", "batch_label", "line_building_stage",
                        "description", "notes", "transgene_base_code", "allele_number",
                        "zygosity", "created_by",
                    }
                    score = sum(1 for h in header_lower if h in expected)
                    size = zf.getinfo(n).file_size
                    candidates.append((score, size, n))
            except Exception:
                # ignore unreadable entries
                continue

        if not candidates:
            # Fall back to any single CSV if exactly one non-junk CSV exists
            csv_names = [n for n in names if n.lower().endswith(".csv")]
            if len(csv_names) == 1:
                n = csv_names[0]
                return n, zf.read(n)
            # Give a helpful error
            found = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            raise ValueError(
                "ZIP should contain exactly one CSV with a 'fish_name' header. "
                f"Found CSVs: {found or 'none'}"
            )

        # Pick best candidate: highest score, then largest size
        candidates.sort(reverse=True)  # sorts by score desc, then size desc, then name desc
        _, _, best = candidates[0]
        return best, zf.read(best)

def get_csv_bytes_and_batch(uploaded_file) -> tuple[bytes, str, str]:
    """
    Returns (csv_bytes, batch_id, source_label).
    If ZIP: pull CSV inside, batch from ZIP filename.
    If CSV: use file directly, batch from CSV filename.
    """
    fname = uploaded_file.name
    if fname.lower().endswith(".zip"):
        inner_name, csv_bytes = _extract_csv_from_zip(uploaded_file.getvalue())
        batch = infer_batch_from_filename(fname)
        return csv_bytes, batch, f"ZIP:{fname} → {inner_name}"
    else:
        return uploaded_file.getvalue(), infer_batch_from_filename(fname), f"CSV:{fname}"

# ---------- CSV normalization ----------
def _normalize_csv(bytes_in: bytes, seed_batch_id: str) -> str:
    """
    Read user CSV in any order, fill missing cols (including seed_batch_id), drop extras,
    order to REQUIRED_ORDER, parse/format dates, and return CSV text with header.
    """
    df = pd.read_csv(io.BytesIO(bytes_in), dtype=str).fillna("")
    # Ensure seed_batch_id exists and is filled with inferred batch
    if "seed_batch_id" not in df.columns:
        df["seed_batch_id"] = seed_batch_id
    else:
        df["seed_batch_id"] = df["seed_batch_id"].apply(lambda s: s if str(s).strip() else seed_batch_id)

    # Normalize date into birth_date (strict field); ignore legacy synonyms if present
    if "birth_date" in df.columns:
        bd = pd.to_datetime(df["birth_date"], errors="coerce", infer_datetime_format=True)
        df["birth_date"] = bd.dt.strftime("%Y-%m-%d")
    else:
        df["birth_date"] = ""

    # Add any missing required columns as blank strings
    for c in REQUIRED_ORDER:
        if c not in df.columns:
            df[c] = ""

    # Keep only required columns and order them
    df = df[REQUIRED_ORDER]

    # Output CSV text
    out = io.StringIO()
    df.to_csv(out, index=False)
    return out.getvalue()

# ---------- psycopg3 COPY helper ----------
def _copy_csv_text(conn, copy_sql: str, csv_text: str) -> None:
    # NULL '' ensures empty strings become SQL NULLs
    with conn.cursor().copy(copy_sql) as cp:
        cp.write(csv_text)

# --- replace your existing stage_into_raw with this version ---
NULL_TOKENS = {"na", "n/a", "none"}  # strings we’ll treat as empty/NULL
# --- replace your existing stage_into_raw with this version ---
def stage_into_raw(conn, fish_csv_bytes: bytes, seed_batch_id: str) -> None:
    """
    Clean incoming CSV:
      - robust decode
      - normalize headers (lower + spaces->underscores)
      - strip whitespace
      - map NA/N/A/None -> empty string (then COPY NULL '')
      - parse birth_date to YYYY-MM-DD
      - coerce allele_number to '' unless it's an integer
      - fill/override seed_batch_id
      - keep only expected columns in the right order
    Then COPY into raw.wide_fish_upload using NULL ''.
    """
    import io
    import pandas as pd

    EXPECTED = [
        "seed_batch_id", "fish_name", "nickname", "birth_date",
        "background_strain", "strain", "batch_label", "line_building_stage",
        "description", "notes", "transgene_base_code", "allele_number",
        "allele_label_legacy", "zygosity", "created_by",
    ]

    # 1) decode (utf-8 -> latin-1 fallback)
    try:
        text = fish_csv_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = fish_csv_bytes.decode("latin-1")

    # 2) load all columns as strings (no NA magic from pandas)
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, na_filter=False)

    # 3) normalize headers: trim, lower, spaces->underscores
    df.rename(columns={c: c.strip().lower().replace(" ", "_") for c in df.columns}, inplace=True)

    # 4) strip whitespace cell-wise
    df = df.applymap(lambda v: v.strip() if isinstance(v, str) else v)

    # 5) normalize common NULL tokens -> empty string
    df = df.applymap(lambda v: "" if isinstance(v, str) and v.lower() in NULL_TOKENS else v)

    # 6) ensure all expected columns exist; add missing as empty
    for col in EXPECTED:
        if col not in df.columns:
            df[col] = ""

    # 7) birth_date -> YYYY-MM-DD (coerce failures to empty)
    if "birth_date" in df.columns:
        bd = pd.to_datetime(df["birth_date"], errors="coerce", dayfirst=False, infer_datetime_format=True)
        df["birth_date"] = bd.dt.strftime("%Y-%m-%d").fillna("")

    # 8) allele_number -> keep only clean integers; otherwise empty
    def _clean_int(s: str) -> str:
        s = s.strip()
        # allow things like "001" -> "1"; reject blanks/garbage -> ""
        return str(int(s)) if s.isdigit() else ""  # int() normalizes leading zeros
    df["allele_number"] = df["allele_number"].apply(_clean_int)

    # 9) zygosity -> normalized set (else 'unknown' if non-empty junk; keep empty if blank)
    def _norm_zyg(z: str) -> str:
        z0 = z.strip().lower()
        if not z0:
            return ""
        return z0 if z0 in {"homozygous", "heterozygous", "unknown"} else "unknown"
    df["zygosity"] = df["zygosity"].apply(_norm_zyg)

    # 10) seed_batch_id: fill blanks with inferred batch
    if seed_batch_id:
        df.loc[df["seed_batch_id"].eq(""), "seed_batch_id"] = seed_batch_id

    # 11) keep only EXPECTED columns (order matters for COPY)
    df = df[EXPECTED]

    # 12) write back to CSV
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    # 13) stage then COPY with NULL '' so empty strings become SQL NULLs
    with conn.cursor() as cur:
        cur.execute("truncate raw.wide_fish_upload")
        copy_sql = (
            "COPY raw.wide_fish_upload("
            " seed_batch_id,fish_name,nickname,birth_date,"
            " background_strain,strain,batch_label,line_building_stage,"
            " description,notes,transgene_base_code,allele_number,"
            " allele_label_legacy,zygosity,created_by"
            ") FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')"
        )
        with cur.copy(copy_sql) as cp:
            cp.write(buf.getvalue())
            
# ---------- Validation / Load runners ----------
def run_validate(conn) -> None:
    sql = VALIDATE.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        for _stmt in (s.strip() for s in sql.split(";") if s.strip()):
            cur.execute(_stmt)

def run_load(conn) -> None:
    sql = LOAD.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        for _stmt in (s.strip() for s in sql.split(";") if s.strip()):
            cur.execute(_stmt)

# ---------- Preview (resolved, grouped, no inserts) ----------
st.subheader("Preview (staged only, no inserts)")
if st.button("Preview mapping"):
    if not uploaded:
        st.warning("Upload a ZIP or CSV first.")
    else:
        try:
            csv_bytes, batch_id, src = get_csv_bytes_and_batch(uploaded)
            with get_conn() as conn:
                # Stage first
                stage_into_raw(conn, csv_bytes, batch_id)

                # (optional) capture staged names for debugging the preview
                with conn.cursor() as cur:
                    cur.execute("""
                        select distinct trim(fish_name)
                        from raw.wide_fish_upload
                        where trim(coalesce(fish_name,'')) <> ''
                    """)
                    staged_names = [r[0] for r in cur.fetchall()]

                preview_sql = """
with base as (
  select distinct
    seed_batch_id, fish_name, nickname, birth_date,
    background_strain, strain, batch_label, line_building_stage,
    description, notes
  from raw.wide_fish_upload
),
links as (
  select
    trim(seed_batch_id) as seed_batch_id,
    trim(fish_name)     as fish_name,
    trim(transgene_base_code) as base,
    allele_number as num,
    lower(coalesce(trim(zygosity),'unknown')) as z
  from raw.wide_fish_upload
  where trim(coalesce(transgene_base_code,'')) <> ''
    and allele_number is not null
)
select
  b.seed_batch_id, b.fish_name, b.nickname, b.birth_date,
  b.background_strain, b.strain, b.batch_label, b.line_building_stage,
  b.description, b.notes,
  coalesce(
    json_agg(
      json_build_object('base', l.base, 'allele', l.num, 'zygosity', l.z)
      order by l.base, l.num
    ) filter (where l.base is not null),
    '[]'::json
  ) as alleles_json,
  string_agg(
    l.base || '-' || l.num::text || ' (' || l.z || ')',
    ', ' order by l.base, l.num
  ) filter (where l.base is not null) as alleles_label
from base b
left join links l
  on l.seed_batch_id = b.seed_batch_id
 and l.fish_name     = b.fish_name
group by
  b.seed_batch_id, b.fish_name, b.nickname, b.birth_date,
  b.background_strain, b.strain, b.batch_label, b.line_building_stage,
  b.description, b.notes
order by b.fish_name;
"""
                with conn.cursor() as cur:
                    cur.execute(preview_sql)
                    rows = cur.fetchall()
                    cols = [d.name for d in cur.description]

            df_prev = pd.DataFrame(rows, columns=cols)
            st.caption(f"Source: {src}  •  Inferred batch_id: `{batch_id}`")
            if df_prev.empty:
                st.info("No resolvable allele links (check base/allele_number columns).")
            else:
                st.dataframe(df_prev, use_container_width=True)

            # Clean stage
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute("truncate raw.wide_fish_upload")

        except Exception as e:
            st.error(f"Preview failed: {e}")

st.divider()

# ---------- One-click: Upload → Validate → Load → Report ----------
st.subheader("Upload & Load (one click)")
if st.button("Upload, validate, load, and show report"):
    if not uploaded:
        st.warning("Upload a ZIP or CSV first.")
    else:
        try:
            csv_bytes, batch_id, src = get_csv_bytes_and_batch(uploaded)
            with get_conn() as conn:
                # 1) Stage & validate
                stage_into_raw(conn, csv_bytes, batch_id)

                # Capture staged names now (before validate/load may touch the stage)
                with conn.cursor() as cur:
                    cur.execute("""
                        select distinct trim(fish_name)
                        from raw.wide_fish_upload
                        where trim(coalesce(fish_name,'')) <> ''
                    """)
                    staged_names = [r[0] for r in cur.fetchall()]
                lc_names = [s.strip().lower() for s in staged_names]

                run_validate(conn)
                run_load(conn)

                # 2) Log this batch using captured names
                with conn.cursor() as cur:
                    cur.execute("""
                        create table if not exists public.load_log_fish(
                          seed_batch_id text not null,
                          fish_id uuid not null,
                          logged_at timestamptz default now(),
                          primary key (seed_batch_id, fish_id, logged_at)
                        );
                    """)
                    logged = 0
                    if lc_names:
                        cur.execute("""
                            insert into public.load_log_fish(seed_batch_id, fish_id)
                            select %s::text, f.id
                            from public.fish f
                            where lower(trim(f.name)) = any(%s)
                            on conflict do nothing;
                        """, (batch_id, lc_names))
                        logged = cur.rowcount or 0

                    # clear stage last
                    cur.execute("truncate raw.wide_fish_upload")

                # >>>> KEY LINE: make results visible to any subsequent reads <<<<
                conn.commit()

                # 3) Report (use the SAME committed connection so we 100% see the rows)
                with conn.cursor() as cur:
                    cur.execute("""
                        with fib as (
                          select distinct fish_id
                          from public.load_log_fish
                          where seed_batch_id = %s
                        )
                        select
                          (select count(*) from fib) as fish_count,
                          (select count(*)
                             from public.fish_transgene_alleles fta
                             join fib on fib.fish_id = fta.fish_id) as allele_links;
                    """, (batch_id,))
                    fish_count, link_count = cur.fetchone()

                    cur.execute("""
                        with fib as (
                          select distinct fish_id
                          from public.load_log_fish
                          where seed_batch_id = %s
                        )
                        select
                          f.fish_code,
                          f.name,
                          coalesce((
                            select count(*) from public.fish_transgene_alleles fta
                            where fta.fish_id = f.id
                          ),0) as allele_links
                        from fib
                        join public.fish f on f.id = fib.fish_id
                        order by f.name;
                    """, (batch_id,))
                    rows = cur.fetchall()
                    cols = [d.name for d in cur.description]

            # 4) UI
            st.success("Loaded to DB 🎉")
            st.write(f"Logged **{logged}** fish into `load_log_fish` for this batch.")
            st.caption(f"Source: {src} • Inferred batch_id: `{batch_id}`")
            st.write(f"**Report:** {fish_count} fish, {link_count} allele links")
            st.dataframe(pd.DataFrame(rows, columns=cols), use_container_width=True)
            st.session_state["last_batch_id"] = batch_id

        except Exception as e:
            st.error(f"Load failed: {e}")
            st.caption(f"Source: {src} • Inferred batch_id: `{batch_id}`")

            # === Simple, reliable report (no staging dependency) ===
            with get_conn() as conn, conn.cursor() as cur:
                # 1) Count distinct fish in this batch straight from the log
                cur.execute("""
                    with fib as (
                    select distinct fish_id
                    from public.load_log_fish
                    where seed_batch_id = %s
                    )
                    select
                    (select count(*) from fib) as fish_count,
                    (select count(*) from public.fish_transgene_alleles fta
                        join fib on fib.fish_id = fta.fish_id) as allele_links;
                """, (batch_id,))
                fish_count, link_count = cur.fetchone()

            st.write(f"**Report:** {fish_count} fish, {link_count} allele links")

            # 2) Show the fish list (with link counts) for this batch
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute("""
                    with fib as (
                    select distinct fish_id
                    from public.load_log_fish
                    where seed_batch_id = %s
                    )
                    select
                    f.fish_code,
                    f.name,
                    coalesce((
                        select count(*) from public.fish_transgene_alleles fta
                        where fta.fish_id = f.id
                    ), 0) as allele_links
                    from fib
                    join public.fish f on f.id = fib.fish_id
                    order by f.name;
                """, (batch_id,))
                rows = cur.fetchall()
                cols = [d.name for d in cur.description]

            st.dataframe(pd.DataFrame(rows, columns=cols), use_container_width=True)

        except Exception as e:
            st.error(f"Load failed: {e}")

# ---------- Most recent loaded batch ----------
st.subheader("Most recent loaded batch")
try:
    desired = st.session_state.get("last_batch_id")
    with get_conn() as conn, conn.cursor() as cur:
        if not desired:
            cur.execute("""
                select seed_batch_id
                from public.load_log_fish
                order by logged_at desc
                limit 1
            """)
            row = cur.fetchone()
            desired = row[0] if row else None

        if not desired:
            st.info("No batches have been logged yet. Load a batch to see it here.")
        else:
            st.caption(f"Showing batch_id: `{desired}`")
            cur.execute("""
                with fish_in_batch as (
                  select llf.fish_id, max(llf.logged_at) as max_logged_at
                  from public.load_log_fish llf
                  where llf.seed_batch_id = %s
                  group by llf.fish_id
                )
                select
                  f.fish_code,
                  f.name,
                  count(fta.*) as allele_links,
                  max(f.created_at) as created_at
                from fish_in_batch fib
                join public.fish f on f.id = fib.fish_id
                left join public.fish_transgene_alleles fta on fta.fish_id = f.id
                group by f.fish_code, f.name
                order by created_at desc nulls last, f.name;
            """, (desired,))
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            df_recent = pd.DataFrame(rows, columns=cols)
            if "created_at" in df_recent.columns:
                df_recent = df_recent.drop(columns=["created_at"])
            st.dataframe(df_recent, use_container_width=True)
except Exception as e:
    st.info(f"Batch summary unavailable: {e}")