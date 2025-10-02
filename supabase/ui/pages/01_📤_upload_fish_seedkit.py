from __future__ import annotations

# 01_📤_upload_fish_seedkit.py

import csv, io, os, shlex, sys, tempfile, subprocess
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, quote as urlquote

import pandas as pd
import streamlit as st
from sqlalchemy import text, create_engine

# 🔒 auth gate
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock

PAGE_TITLE = "Upload Fish Seedkit (Fish + Linking Only) — DB-aligned"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
require_app_unlock()
st.title("📤 Upload Fish Seedkit")

# Canonical schema headers (no backward-compat: require allele_nickname)
COLUMNS_CANONICAL: List[str] = [
    "name",
    "line_building_stage",
    "nickname",
    "strain",
    "date_of_birth",
    "description",
    "transgene_base_code",
    "allele_nickname",      # ← use this only
    "zygosity",
    "created_by",
]
REQUIRED_MINIMAL: List[str] = ["name", "strain", "line_building_stage"]
TREATMENT_HINTS = {
    "treatment_type","performed_at","injected_plasmids","plasmids_injected",
    "plasmid_amount","plasmid_units","rna_amount","rna_units","dose","concentration","vehicle",
}
ALLOWED_LINE_STAGES = {"founder","F0","F1","F2","F3","unknown"}
ALLOWED_ZYGOSITY = {"heterozygous","homozygous","unknown",""}

@st.cache_resource(show_spinner=False)
def _engine():
    return create_engine(build_db_url(), pool_pre_ping=True, future=True, connect_args={"prepare_threshold": None})

def get_loader_path() -> Path:
    default = Path(__file__).resolve().parents[3] / "scripts" / "seedkit_load_wide.py"
    env_override = os.getenv("SEEDKIT_WIDE_LOADER", "").strip()
    if env_override:
        p = Path(env_override)
        if p.exists():
            return p
    return default

def _ensure_sslmode(url: str) -> str:
    u = urlparse(url)
    host = (u.hostname or "").lower() if u.hostname else ""
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    if host in {"localhost","127.0.0.1","::1"}:
        q["sslmode"] = "disable"
    else:
        q.setdefault("sslmode", "require")
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))

def parse_dsn_to_url(dsn: str) -> str:
    parts = shlex.split(dsn)
    kv = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            kv[k.strip()] = v.strip()
    host = kv.pop("host", "")
    port = kv.pop("port", "")
    dbname = kv.pop("dbname", "")
    user = kv.pop("user", "")
    password = kv.pop("password", "")
    netloc = ""
    if user:
        netloc += urlquote(user)
        if password:
            netloc += f":{urlquote(password)}"
        netloc += "@"
    if host:
        netloc += host
    if port:
        netloc += f":{port}"
    path = f"/{dbname}" if dbname else ""
    query = urlencode(kv, doseq=True)
    return urlunparse(("postgresql", netloc, path, "", query, ""))

def build_db_url() -> str:
    raw = (st.secrets.get("DB_URL") or os.getenv("DATABASE_URL") or "").strip()
    if raw:
        url = parse_dsn_to_url(raw) if "://" not in raw else raw
        return _ensure_sslmode(url)
    required = ["PGHOST","PGPORT","PGDATABASE","PGUSER","PGPASSWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError("Missing DB env vars: " + ", ".join(missing))
    url = (
        "postgresql://"
        f"{urlquote(os.getenv('PGUSER',''))}:{urlquote(os.getenv('PGPASSWORD',''))}"
        f"@{os.getenv('PGHOST')}:{os.getenv('PGPORT')}/{os.getenv('PGDATABASE')}"
    )
    return _ensure_sslmode(url)

def _mask_url_password(url: str) -> str:
    u = urlparse(url)
    netloc = u.netloc
    if "@" in netloc:
        creds, host = netloc.split("@", 1)
        if ":" in creds:
            user = creds.split(":", 1)[0]
            netloc = f"{user}:***@{host}"
    return u._replace(netloc=netloc).geturl()

def _norm_header_list(cols: List[str]) -> List[str]:
    return [(c or "").strip() for c in cols]

def validate_df(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    for c in df.columns:
        if pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].astype(str).str.strip()

    cols = _norm_header_list(list(df.columns))

    # Required minimal
    missing = [c for c in REQUIRED_MINIMAL if c not in cols]
    if missing:
        errors.append("Missing required columns: " + ", ".join(f"`{c}`" for c in missing))

    # No treatment columns
    bad_treatment = [c for c in cols if c in TREATMENT_HINTS]
    if bad_treatment:
        errors.append("Treatment-related columns are not allowed here: " + ", ".join(f"`{c}`" for c in sorted(bad_treatment)))

    # Backward compat intentionally dropped: require allele_nickname when transgene_base_code present
    if "transgene_base_code" in cols and "allele_nickname" not in cols:
        errors.append("`allele_nickname` is required when `transgene_base_code` is present (no backward compatibility).")

    # Content checks
    if "name" in df.columns:
        names = df["name"].astype(str).str.strip()
        if names.eq("").any():
            errors.append("Some rows have an empty `name`.")
        dups = names[names.duplicated(keep=False)]
        if not dups.empty:
            examples = sorted(set(dups.tolist()))[:5]
            warnings.append(f"Duplicate `name` values (rows will upsert): {examples}")

    if "line_building_stage" in df.columns:
        bad = ~df["line_building_stage"].astype(str).str.strip().isin(ALLOWED_LINE_STAGES)
        if bad.any():
            warnings.append("`line_building_stage` recommended: founder, F0, F1, F2, F3, unknown.")

    if "zygosity" in df.columns:
        badz = ~df["zygosity"].astype(str).str.strip().isin(ALLOWED_ZYGOSITY)
        if badz.any():
            warnings.append("`zygosity` should be one of: heterozygous, homozygous, unknown.")

    # If allele_nickname exists, ensure no blanks for rows with a base
    if {"transgene_base_code", "allele_nickname"}.issubset(cols):
        mask_base = df["transgene_base_code"].astype(str).str.strip().ne("")
        mask_name = df["allele_nickname"].astype(str).str.strip().ne("")
        if (mask_base & ~mask_name).any():
            errors.append("Rows with `transgene_base_code` must include non-empty `allele_nickname`.")

    # Order preview
    ordered = [c for c in COLUMNS_CANONICAL if c in df.columns]
    trailing = [c for c in df.columns if c not in ordered]
    df = df[ordered + trailing] if trailing else df
    return df, errors, warnings

def upsert_fish_seed_batches_by_codes(engine, fish_codes, seed_batch_id: str, fish_names=None):
    codes_norm = [str(c).strip().upper() for c in (fish_codes or []) if str(c).strip()]
    names_norm = [str(n).strip().upper() for n in (fish_names or []) if str(n).strip()]
    if not codes_norm and not names_norm:
        return
    with engine.begin() as cx:
        cx.execute(
            text("""
                INSERT INTO public.seed_batches(seed_batch_id, batch_label)
                VALUES (:id, :label)
                ON CONFLICT (seed_batch_id) DO NOTHING
            """),
            {"id": seed_batch_id, "label": seed_batch_id},
        )
        fish_ids = cx.execute(
            text("""
                SELECT DISTINCT f.id_uuid
                FROM public.fish f
                WHERE
                  (:use_codes AND UPPER(TRIM(f.fish_code)) = ANY(:codes))
                  OR
                  (:use_names AND UPPER(TRIM(f.name)) = ANY(:names))
            """),
            {"codes": codes_norm or [], "names": names_norm or [],
             "use_codes": bool(codes_norm), "use_names": bool(names_norm)},
        ).scalars().all()
        if not fish_ids:
            return
        cx.execute(
            text("""
                INSERT INTO public.fish_seed_batches (fish_id, seed_batch_id, updated_at)
                VALUES (:fish_id, :seed_batch_id, now())
                ON CONFLICT (fish_id) DO UPDATE
                  SET seed_batch_id = EXCLUDED.seed_batch_id,
                      updated_at    = EXCLUDED.updated_at
            """),
            [{"fish_id": fid, "seed_batch_id": seed_batch_id} for fid in fish_ids],
        )

def overwrite_created_by_from_csv(engine, df: pd.DataFrame) -> None:
    if "created_by" not in df.columns:
        return
    if "fish_code" in df.columns:
        pairs = [
            (str(c).strip().upper(), str(cb).strip())
            for c, cb in zip(df["fish_code"], df["created_by"])
            if str(c).strip() and str(cb).strip()
        ]
    else:
        pairs = [
            (str(n).strip().upper(), str(cb).strip())
            for n, cb in zip(df["name"], df["created_by"])
            if str(n).strip() and str(cb).strip()
        ]
    if not pairs:
        return
    params = [{"key": k, "creator": v} for k, v in pairs]
    with engine.begin() as cx:
        cx.execute(
            text("""
                UPDATE public.fish f
                SET created_by = :creator
                WHERE (f.created_by IS DISTINCT FROM :creator)
                  AND (
                        UPPER(TRIM(f.fish_code)) = :key
                     OR UPPER(TRIM(f.name))      = :key
                  )
            """),
            params,
        )

def upsert_canonical_from_csv(engine, df: pd.DataFrame, code_prefix: str = "abc") -> tuple[int,int]:
    """
    CSV → canonical:
      allele_name   := df['allele_nickname'] (human label)
      allele_number := 1..N per base (sorted by allele_name, case-insensitive)
      allele_code   := f"{code_prefix}-{allele_number}"
      writes transgene_alleles and fish_transgene_alleles (FK-safe: auto-detect fish PK)
      DEFAULT ZYGOSITY: 'unknown'
    """
    if "transgene_base_code" not in df.columns or "allele_nickname" not in df.columns:
        return (0, 0)

    base = df["transgene_base_code"].astype(str).str.strip()
    name_series = df["allele_nickname"].astype(str).str.strip()  # no fallback (no backward-compat)

    # fish key from CSV
    if "fish_code" in df.columns:
        key_series = df["fish_code"]
    elif "name" in df.columns:
        key_series = df["name"]
    else:
        return (0, 0)

    # DEFAULT zygosity = 'unknown'
    zyg_series = df.get("zygosity", pd.Series(["unknown"] * len(df))).astype(str).str.strip().replace({"": "unknown"})

    # materialize clean rows
    rows = []
    for k, b, nm, z in zip(key_series, base, name_series, zyg_series):
        k = str(k).strip().upper()
        b = str(b).strip()
        nm = str(nm).strip()
        z = (str(z).strip() or "unknown")
        if k and b and nm:
            rows.append((k, b, nm, z))
    if not rows:
        return (0, 0)

    # build 1..N per base from distinct names (deterministic by lower(name))
    by_base: dict[str, set] = {}
    for _, b, nm, _ in rows:
        by_base.setdefault(b, set()).add(nm)
    ordered_map: dict[tuple[str, str], int] = {}
    for b, labels in by_base.items():
        for i, nm in enumerate(sorted(labels, key=lambda s: s.lower()), start=1):
            ordered_map[(b, nm)] = i

    # canonical allele defs
    allele_defs = [{"base": b, "num": n, "code": f"{code_prefix}-{n}", "name": nm}
                   for (b, nm), n in ordered_map.items()]

    # fish links (key, base, num, zyg)
    links = []
    for k, b, nm, z in rows:
        n = ordered_map.get((b, nm))
        if n:
            links.append({"key": k, "base": b, "num": n, "zyg": z})

    with engine.begin() as cx:
        # 1) upsert canonical defs
        cx.execute(
            text("""
                INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_code, allele_name)
                VALUES (:base, :num, :code, :name)
                ON CONFLICT (transgene_base_code, allele_number) DO UPDATE
                  SET allele_code = EXCLUDED.allele_code,
                      allele_name = EXCLUDED.allele_name
            """),
            allele_defs,
        )

        # 2) detect which fish column the FK references ('id' vs 'id_uuid'), fallback to PK if needed
        fk_target = cx.execute(text("""
            SELECT att2.attname AS ref_col
            FROM pg_constraint c
            JOIN pg_class      cl    ON cl.oid  = c.conrelid  AND cl.relname = 'fish_transgene_alleles'
            JOIN pg_class      rf    ON rf.oid  = c.confrelid AND rf.relname = 'fish'
            JOIN pg_attribute  att2  ON att2.attrelid = c.confrelid AND att2.attnum = ANY (c.confkey)
            WHERE c.contype = 'f'
            LIMIT 1
        """)).scalar()

        if not fk_target:
            # fallback: primary key column on fish
            fk_target = cx.execute(text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema    = tc.table_schema
                 AND kcu.table_name      = tc.table_name
                WHERE tc.table_schema = 'public'
                  AND tc.table_name   = 'fish'
                  AND tc.constraint_type = 'PRIMARY KEY'
                LIMIT 1
            """)).scalar() or "id"

        # 3) link fish → canonical using the detected FK target column
        link_sql = f"""
            INSERT INTO public.fish_transgene_alleles
                (fish_id, transgene_base_code, allele_number, zygosity, created_at)
            SELECT f.{fk_target}, d.base, d.num, d.zyg, now()
            FROM (SELECT :key AS key, :base AS base, :num AS num, :zyg AS zyg) d
            JOIN public.fish f
              ON UPPER(TRIM(f.fish_code)) = d.key
               OR UPPER(TRIM(f.name))      = d.key
            ON CONFLICT (fish_id, transgene_base_code, allele_number) DO NOTHING
        """
        if links:
            cx.execute(text(link_sql), links)

    return (len(allele_defs), len(links))

# Example download (update header to allele_nickname)
with st.expander("📥 Download example filled-out CSV", expanded=False):
    ex = io.StringIO()
    writer = csv.DictWriter(ex, fieldnames=[
        "name","nickname","date_of_birth","strain","line_building_stage","description",
        "transgene_base_code","allele_nickname","zygosity","created_by"
    ])
    writer.writeheader()
    writer.writerow({
        "name":"mem-tdmSG-8m","nickname":"mem-8m","date_of_birth":"2025-09-20","strain":"casper",
        "line_building_stage":"founder","description":"import via page",
        "transgene_base_code":"pDQM005","allele_nickname":"301","zygosity":"unknown","created_by":"dqm"
    })
    writer.writerow({
        "name":"mem-tdmSG-11m","nickname":"mem-11m","date_of_birth":"2025-09-20","strain":"casper",
        "line_building_stage":"founder","description":"import via page",
        "transgene_base_code":"pDQM005","allele_nickname":"302","zygosity":"unknown","created_by":"dqm"
    })
    st.download_button("Download example CSV", ex.getvalue().encode("utf-8"),
                       file_name="fish_seedkit_example.csv", mime="text/csv")

# Controls
q = st.text_input("Search (preview only)", placeholder="name, nickname, strain…")
with st.expander("Filters (preview only)", expanded=False):
    pass

# Upload widget
left, right = st.columns([2,1])
with left:
    uploaded = st.file_uploader("Upload CSV (DB-aligned headers only)", type=["csv"], accept_multiple_files=False)
with right:
    dry_run = st.checkbox("Dry run (no DB changes)", value=True)

# Process
if uploaded is not None:
    try:
        df = pd.read_csv(uploaded, dtype=str).fillna("")
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        st.stop()

    df, errs, warns = validate_df(df)
    if errs:
        st.error("Please fix the following before loading:")
        for m in errs: st.markdown(f"- ❌ {m}")
        st.stop()
    if warns:
        with st.expander("Warnings (non-blocking)", expanded=False):
            for m in warns: st.markdown(f"- ⚠️ {m}")

    st.subheader("Preview")
    st.dataframe(df.head(50), use_container_width=True)
    seed_batch_id = Path(uploaded.name).stem.strip()

    run = st.button("Run loader" if dry_run else "Load to database", type="primary")
    if run:
        try:
            db_url = build_db_url()
        except Exception as e:
            st.error(str(e)); st.stop()

        loader_path = get_loader_path()
        if not loader_path.exists():
            st.error(f"Loader script not found at: {loader_path}"); st.stop()

        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".csv") as tmp:
            df.to_csv(tmp.name, index=False); tmp_csv = tmp.name

        cmd = [sys.executable, str(loader_path), "--db", db_url, "--csv", tmp_csv]
        if dry_run: cmd.append("--dry-run")

        masked_cmd = " ".join(cmd).replace(db_url, _mask_url_password(db_url))
        st.write("**Command**"); st.code(masked_cmd)

        with st.status("Running loader…", expanded=True) as status:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            st.write("**stdout**"); st.code(proc.stdout or "(empty)")
            st.write("**stderr**"); st.code(proc.stderr or "(empty)")

            if proc.returncode == 0:
                status.update(label="Done", state="complete")
                if dry_run:
                    st.success("Dry run OK ✅")
                else:
                    try:
                        uploaded_codes=(df["fish_code"].astype(str).tolist() if "fish_code" in df.columns else [])
                        uploaded_names=(df["name"].astype(str).tolist() if "name" in df.columns else [])
                        upsert_fish_seed_batches_by_codes(_engine(), uploaded_codes, seed_batch_id, fish_names=uploaded_names)

                        overwrite_created_by_from_csv(_engine(), df)

                        # Canonical: name from CSV (allele_nickname), number = 1..N per base, code = 'abc-<num>'
                        defs, links = upsert_canonical_from_csv(_engine(), df, code_prefix="abc")
                        st.info(f"Canonical upserted: {defs} allele defs, {links} fish links")

                        st.success("Load complete ✅ — batch labels, created_by, and canonical transgene fields updated")
                    except Exception as e:
                        st.warning(f"Post-load step hit an issue: {e}")
            else:
                status.update(label="Failed", state="error")
                st.error(f"Loader exited with code {proc.returncode}")

st.divider()
st.caption(
    "CSV must include `allele_nickname` (no backward compatibility). "
    "Importer writes canonical: allele_name from CSV, allele_number auto 1..N per base, allele_code = 'abc-<number>'. "
    "Zygosity defaults to 'unknown' when omitted."
)