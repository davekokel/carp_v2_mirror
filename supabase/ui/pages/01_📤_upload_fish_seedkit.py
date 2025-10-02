from __future__ import annotations

# 01_📤_upload_fish_seedkit.py

import csv
import io
import os
import shlex
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, quote as urlquote

import pandas as pd
import streamlit as st

# 🔒 auth gate (import paths for local vs mirror)
try:
    from supabase.ui.auth_gate import require_app_unlock  # deployed/mirror path
except Exception:
    from auth_gate import require_app_unlock  # local path fallback

# ────────────────────────────────────────────────────────────────────────────────
# Streamlit UI
# ────────────────────────────────────────────────────────────────────────────────

PAGE_TITLE = "Upload Fish Seedkit (Fish + Linking Only) — DB-aligned"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
require_app_unlock()

st.title("📤 Upload Fish Seedkit")
st.caption(

with st.expander("📥 Download CSV template (DB-aligned)", expanded=False):
    st.download_button(
        label="Download template (with one example row)",
        data=make_template_csv(),
        file_name="seedkit_fish_linking_DB_aligned_template.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.markdown("**Canonical headers (order not strict):**")
    st.code(", ".join(COLUMNS_CANONICAL), language="text")

    "CSV must use **exact DB column names** (see below). "

    "**No injection treatments are allowed here.** "
    "Note: `batch_label` is **derived from the CSV filename** automatically."
)

# ────────────────────────────────────────────────────────────────────────────────
# DB-ALIGNED CANONICAL SCHEMA (order not strict; headers must match exactly)
# ────────────────────────────────────────────────────────────────────────────────

COLUMNS_CANONICAL: List[str] = [
    # public.fish columns (1:1)
    "name",                # UNIQUE in DB (upsert key)
    "line_building_stage",
    "nickname",
    "strain",
    "date_of_birth",       # YYYY-MM-DD
    "description",

    # linking-only (no treatments here)
    "transgene_base_code", # links to alleles/transgenes
    "allele_label_legacy",
    "zygosity",            # heterozygous | homozygous | unknown

    # audit convenience (optional)
    "created_by",
]

REQUIRED_MINIMAL: List[str] = [
    "name",
    "strain",
    "line_building_stage",
]

# Disallowed here (clear treatment-ish or non-fish/linking)
TREATMENT_HINTS = {
    "treatment_type",
    "performed_at",
    "injected_plasmids",
    "plasmids_injected",
    "plasmid_amount",
    "plasmid_units",
    "rna_amount",
    "rna_units",
    "dose",
    "concentration",
    "vehicle",
    # operator only allowed as CLI flag
    "operator",
}

ALLOWED_LINE_STAGES = {"founder", "F0", "F1", "F2", "F3", "unknown"}
ALLOWED_ZYGOSITY = {"heterozygous", "homozygous", "unknown", ""}

# ────────────────────────────────────────────────────────────────────────────────
# Helpers: loader path, DB URL building (secrets/env, DSN→URL), sslmode, masking
# ────────────────────────────────────────────────────────────────────────────────

def get_loader_path() -> Path:
    """Default: repo_root/parents[3]/scripts/seedkit_load_wide.py; allow env override."""
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
    if host in {"localhost", "127.0.0.1", "::1"}:
        q["sslmode"] = "disable"
    else:
        q.setdefault("sslmode", "require")
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))

def parse_dsn_to_url(dsn: str) -> str:
    """Convert libpq DSN (key=value …) to SQLAlchemy URL."""
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
    """
    Order of precedence:
      1) st.secrets['DB_URL'] (URL or DSN)
      2) env DATABASE_URL (URL or DSN)
      3) PG* env vars (compose URL)
    Always normalize sslmode via _ensure_sslmode().
    """
    raw = (st.secrets.get("DB_URL") or os.getenv("DATABASE_URL") or "").strip()
    if raw:
        url = parse_dsn_to_url(raw) if "://" not in raw else raw
        return _ensure_sslmode(url)

    required = ["PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"]
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
    return urlunparse((u.scheme, netloc, u.path, u.params, u.query, u.fragment))

# ────────────────────────────────────────────────────────────────────────────────
# Template + validation
# ────────────────────────────────────────────────────────────────────────────────

def make_template_csv() -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS_CANONICAL)
    writer.writeheader()
    writer.writerow({
        "name": "mem-tdmSG-13m",
        "line_building_stage": "founder",
        "nickname": "membrane-tandem-mStayGold",
        "strain": "casper",
        "date_of_birth": "2025-09-20",  # YYYY-MM-DD (example filled)
        "description": "import via page",
        "transgene_base_code": "pDQM005",
        "allele_label_legacy": "304",
        "zygosity": "heterozygous",
        "created_by": "dqm",
    })
    return buf.getvalue().encode("utf-8")

def _norm_header_list(cols: List[str]) -> List[str]:
    return [(c or "").strip() for c in cols]

def validate_df(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Returns (possibly re-ordered df, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Normalize string columns
    for c in df.columns:
        if pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].astype(str).str.strip()

    cols = _norm_header_list(list(df.columns))

    # Strict header policy
    missing = [c for c in REQUIRED_MINIMAL if c not in cols]
    if missing:
        errors.append("Missing required columns: " + ", ".join(f"`{c}`" for c in missing))

    unknown = [c for c in cols if c not in COLUMNS_CANONICAL]
    if unknown:
        errors.append("Unsupported columns present (this page only accepts DB-aligned headers): "
                      + ", ".join(f"`{c}`" for c in sorted(unknown)))

    bad_treatment = [c for c in cols if c in TREATMENT_HINTS]
    if bad_treatment:
        errors.append("Treatment-related columns are not allowed here: "
                      + ", ".join(f"`{c}`" for c in sorted(bad_treatment)))

    # Content checks
    if "name" in df.columns:
        names = df["name"].astype(str).str.strip()
        if names.eq("").any():
            errors.append("Some rows have an empty `name`.")
        dups = names[names.duplicated(keep=False)]
        if not dups.empty:
            examples = sorted(set(dups.tolist()))[:5]
            errors.append(f"Duplicate `name` values: {examples}")

    if "line_building_stage" in df.columns:
        bad = ~df["line_building_stage"].astype(str).str.strip().isin(ALLOWED_LINE_STAGES)
        if bad.any():
            warnings.append("`line_building_stage` has non-standard values; "
                            "recommended: founder, F0, F1, F2, F3, unknown.")

    if "zygosity" in df.columns:
        badz = ~df["zygosity"].astype(str).str.strip().isin(ALLOWED_ZYGOSITY)
        if badz.any():
            warnings.append("`zygosity` should be one of: heterozygous, homozygous, unknown.")

    # Pretty preview: put known columns first
    ordered = [c for c in COLUMNS_CANONICAL if c in df.columns]
    trailing = [c for c in df.columns if c not in ordered]
    df = df[ordered + trailing] if trailing else df

    return df, errors, warnings

# Connection preview
with st.expander("Connection", expanded=False):
    try:
        db_url = build_db_url()
    except Exception as e:
        db_url = ""
        st.error(str(e))
    if db_url:
        st.write("DB URL (masked):")
        st.code(_mask_url_password(db_url))
        q = dict(parse_qsl(urlparse(db_url).query, keep_blank_values=True))
        st.caption(f"Resolved sslmode: `{q.get('sslmode', '(none)')}`")

left, right = st.columns([2, 1])
with left:
    uploaded = st.file_uploader(
        "Upload CSV (DB-aligned headers only)",
        type=["csv"],
        accept_multiple_files=False,
        help="Headers must exactly match the DB column names shown above.",
    )
with right:
    dry_run = st.checkbox("Dry run (no DB changes)", value=True)
    operator = st.text_input("Operator (recorded on created/updated rows)", value="streamlit_seedkit")

if uploaded is not None:
    try:
        df = pd.read_csv(uploaded, dtype=str).fillna("")
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        st.stop()

    # Validate and re-order for preview
    df, errs, warns = validate_df(df)

    if errs:
        st.error("Please fix the following before loading:")
        for m in errs:
            st.markdown(f"- ❌ {m}")
        st.stop()

    if warns:
        with st.expander("Warnings (non-blocking)", expanded=False):
            for m in warns:
                st.markdown(f"- ⚠️ {m}")

    st.subheader("Preview")
    st.dataframe(df.head(50), use_container_width=True)

    run = st.button("Run loader" if dry_run else "Load to database", type="primary")
    if run:
        try:
            db_url = build_db_url()
        except Exception as e:
            st.error(str(e))
            st.stop()

        loader_path = get_loader_path()
        if not loader_path.exists():
            st.error(f"Loader script not found at: {loader_path}")
            st.stop()

        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".csv") as tmp:
            df.to_csv(tmp.name, index=False)
            tmp_csv = tmp.name

        cmd = [
            sys.executable,
            str(loader_path),
            "--db", db_url,
            "--csv", tmp_csv,
            "--operator", operator or "streamlit_seedkit",
        ]
        if dry_run:
            cmd.append("--dry-run")

        # Display masked command
        masked_cmd = " ".join(cmd).replace(db_url, _mask_url_password(db_url))
        st.write("**Command**")
        st.code(masked_cmd)

        with st.status("Running loader…", expanded=True) as status:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            st.write("**stdout**")
            st.code(proc.stdout or "(empty)")
            st.write("**stderr**")
            st.code(proc.stderr or "(empty)")

            if proc.returncode == 0:
                status.update(label="Done", state="complete")
                st.success("Dry run OK ✅" if dry_run else "Load complete ✅")
            else:
                status.update(label="Failed", state="error")
                st.error(f"Loader exited with code {proc.returncode}")

st.divider()
st.caption(
    "This page enforces DB-aligned headers only and intentionally rejects any treatment-related columns. "
    "Set DB_URL in Streamlit secrets or use DATABASE_URL/PG* env vars. "
    "Local hosts use sslmode=disable; remote default to sslmode=require."
)