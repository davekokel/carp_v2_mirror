from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# ---------------------------------------------------------------------------
# Engine helper
# ---------------------------------------------------------------------------

def get_engine_from_env(env_var: str = "DB_URL") -> Engine:
    url = os.getenv(env_var, "").strip()
    if not url:
        raise RuntimeError(
            f"{env_var} is not set. Source scripts/use_db.sh and run use_local/use_staging first."
        )
    return create_engine(url)


import re

# ---------------------------------------------------------------------------
# Code normalization (generic prefix + number, e.g. MGCO01, pDQM005, etc.)
# ---------------------------------------------------------------------------

_GENERIC_CODE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*?)-?0*(\d+)$")


def normalize_base_code(raw: str) -> str:
    """
    Normalize construct codes to canonical forms.

    Rule:
      - For codes of the form PREFIX[optional '-']0*DIGITS
          (e.g. MGCO01, mgco-01, pDQM005, pdqm-5):
            → PREFIX-UPPER + '-' + integer(DIGITS) without leading zeros.

        Examples:
          MGCO01    -> MGCO-1
          MGCO-01   -> MGCO-1
          mgco001   -> MGCO-1
          pDQM005   -> PDQM-5
          pdqm-5    -> PDQM-5

      - For anything that does NOT match this pattern, return s.strip() unchanged.
    """
    s = str(raw or "").strip()
    if not s:
        return s
    m = _GENERIC_CODE_RE.match(s)
    if m:
        prefix, digits = m.groups()
        return f"{prefix.upper()}-{int(digits)}"
    return s

# ---------------------------------------------------------------------------
# CSV utilities
# ---------------------------------------------------------------------------

def _load_csv_normalized(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Plasmids
#   Table: public.plasmids
#   Columns: id, code, plasmid_base_code, name, nickname, notes, created_at
# ---------------------------------------------------------------------------

def _normalize_plasmid_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    df = df.copy()

    colmap = {c: c for c in df.columns}

    def pick(src_names: list[str], target: str) -> Optional[str]:
        for s in src_names:
            if s in df.columns:
                colmap[target] = s
                return s
        return None

    base_col = pick(["plasmid_base_code", "base_code", "code", "plasmid_code"], "plasmid_base_code")
    code_col = pick(["code"], "code")
    name_col = pick(["plasmid_name", "name"], "name")
    nick_col = pick(["nickname", "plasmid_nickname"], "nickname")
    notes_col = pick(["notes", "note"], "notes")

    if not base_col:
        raise ValueError(
            "Plasmid CSV is missing a code column. "
            "Expected one of: plasmid_base_code, base_code, code, plasmid_code."
        )

    if not name_col:
        warnings.append("No name column found; plasmids will be loaded with NULL name.")

    out = pd.DataFrame()
    out["plasmid_base_code"] = (
        df[colmap["plasmid_base_code"]]
        .astype(str)
        .apply(normalize_base_code)
    )

    if code_col:
        out["code"] = df[colmap["code"]].astype(str).str.strip()
    else:
        out["code"] = out["plasmid_base_code"]

    if name_col:
        out["name"] = df[colmap["name"]].astype(str).str.strip()
    else:
        out["name"] = ""

    if nick_col:
        out["nickname"] = df[colmap["nickname"]].astype(str).str.strip()
    else:
        out["nickname"] = ""

    if notes_col:
        out["notes"] = df[colmap["notes"]].astype(str).str.strip()
    else:
        out["notes"] = ""

    mask_valid = out["plasmid_base_code"].str.len() > 0
    dropped = len(out) - int(mask_valid.sum())
    if dropped:
        warnings.append(f"Dropped {dropped} row(s) with empty plasmid_base_code.")
    out = out[mask_valid].reset_index(drop=True)

    return out, warnings


def load_plasmids_from_csv(csv_path: str | Path, engine: Optional[Engine] = None) -> dict:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Plasmid CSV not found: {path}")

    df_raw = _load_csv_normalized(path)
    df, warnings = _normalize_plasmid_columns(df_raw)

    if df.empty:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": warnings}

    if engine is None:
        engine = get_engine_from_env()

    unique_codes = df["plasmid_base_code"].unique().tolist()

    with engine.begin() as cx:
        existing_codes = set(
            cx.execute(
                text(
                    """
                    SELECT plasmid_base_code
                    FROM public.plasmids
                    WHERE plasmid_base_code = ANY(:codes)
                    """
                ),
                {"codes": unique_codes},
            ).scalars().all()
        )

    sql = text(
        """
        INSERT INTO public.plasmids
          (plasmid_base_code, code, name, nickname, notes)
        VALUES
          (:base_code, NULLIF(:code, ''), NULLIF(:name, ''), NULLIF(:nickname, ''), NULLIF(:notes, ''))
        ON CONFLICT (plasmid_base_code) DO UPDATE
        SET code     = COALESCE(EXCLUDED.code, public.plasmids.code),
            name     = EXCLUDED.name,
            nickname = EXCLUDED.nickname,
            notes    = EXCLUDED.notes
        """
    )

    inserted = 0
    updated = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            base_code = row["plasmid_base_code"]
            code = row.get("code", "") or base_code
            params = {
                "base_code": base_code,
                "code": code,
                "name": row.get("name", "") or "",
                "nickname": row.get("nickname", "") or "",
                "notes": row.get("notes", "") or "",
            }
            cx.execute(sql, params)
            if base_code in existing_codes:
                updated += 1
            else:
                inserted += 1
                existing_codes.add(base_code)

    return {"rows": len(df), "inserted": inserted, "updated": updated, "warnings": warnings}


# ---------------------------------------------------------------------------
# RNAs
#   Table: public.rnas
#   Columns: id, rna_base_code, name, notes, created_at
# ---------------------------------------------------------------------------

def _normalize_rna_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    df = df.copy()

    colmap = {c: c for c in df.columns}

    def pick(src_names: list[str], target: str) -> Optional[str]:
        for s in src_names:
            if s in df.columns:
                colmap[target] = s
                return s
        return None

    base_col = pick(["rna_base_code", "base_code", "code", "rna_code"], "rna_base_code")
    name_col = pick(["rna_name", "name"], "name")
    notes_col = pick(["notes", "note"], "notes")

    if not base_col:
        raise ValueError(
            "RNA CSV is missing a base code column. "
            "Expected one of: rna_base_code, base_code, code, rna_code."
        )

    if not name_col:
        warnings.append("No name column found; RNAs will be loaded with NULL name.")

    out = pd.DataFrame()
    out["rna_base_code"] = (
        df[colmap["rna_base_code"]]
        .astype(str)
        .apply(normalize_base_code)
    )

    if name_col:
        out["name"] = df[colmap["name"]].astype(str).str.strip()
    else:
        out["name"] = ""

    if notes_col:
        out["notes"] = df[colmap["notes"]].astype(str).str.strip()
    else:
        out["notes"] = ""

    mask_valid = out["rna_base_code"].str.len() > 0
    dropped = len(out) - int(mask_valid.sum())
    if dropped:
        warnings.append(f"Dropped {dropped} row(s) with empty rna_base_code.")
    out = out[mask_valid].reset_index(drop=True)

    return out, warnings


def load_rnas_from_csv(csv_path: str | Path, engine: Optional[Engine] = None) -> dict:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"RNA CSV not found: {path}")

    df_raw = _load_csv_normalized(path)
    df, warnings = _normalize_rna_columns(df_raw)

    if df.empty:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": warnings}

    if engine is None:
        engine = get_engine_from_env()

    unique_codes = df["rna_base_code"].unique().tolist()

    with engine.begin() as cx:
        existing_codes = set(
            cx.execute(
                text(
                    """
                    SELECT rna_base_code
                    FROM public.rnas
                    WHERE rna_base_code = ANY(:codes)
                    """
                ),
                {"codes": unique_codes},
            ).scalars().all()
        )

    sql = text(
        """
        INSERT INTO public.rnas
          (rna_base_code, name, notes)
        VALUES
          (:base_code, NULLIF(:name, ''), NULLIF(:notes, ''))
        ON CONFLICT (rna_base_code) DO UPDATE
        SET name  = EXCLUDED.name,
            notes = EXCLUDED.notes
        """
    )

    inserted = 0
    updated = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            base_code = row["rna_base_code"]
            params = {
                "base_code": base_code,
                "name": row.get("name", "") or "",
                "notes": row.get("notes", "") or "",
            }
            cx.execute(sql, params)
            if base_code in existing_codes:
                updated += 1
            else:
                inserted += 1
                existing_codes.add(base_code)

    return {"rows": len(df), "inserted": inserted, "updated": updated, "warnings": warnings}


# ---------------------------------------------------------------------------
# Dyes
#   Table: public.dyes
#   Columns: id, dye_base_code, name, notes, created_at
# ---------------------------------------------------------------------------

def _normalize_dye_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    df = df.copy()

    colmap = {c: c for c in df.columns}

    def pick(src_names: list[str], target: str) -> Optional[str]:
        for s in src_names:
            if s in df.columns:
                colmap[target] = s
                return s
        return None

    base_col = pick(["dye_base_code", "base_code", "code", "dye_code"], "dye_base_code")

    used_nickname_as_base = False
    if not base_col and "nickname" in df.columns:
        colmap["dye_base_code"] = "nickname"
        base_col = "nickname"
        used_nickname_as_base = True
        warnings.append("Using 'nickname' column as dye_base_code for dyes CSV.")

    if not base_col:
        raise ValueError(
            "Dye CSV is missing a base code column. "
            "Expected one of: dye_base_code, base_code, code, dye_code, or nickname."
        )

    name_col = pick(["dye_name", "name"], "name")
    notes_col = pick(["notes", "note"], "notes")

    out = pd.DataFrame()
    out["dye_base_code"] = (
        df[colmap["dye_base_code"]]
        .astype(str)
        .apply(normalize_base_code)
    )

    if name_col:
        out["name"] = df[colmap["name"]].astype(str).str.strip()
    else:
        out["name"] = out["dye_base_code"] if used_nickname_as_base else ""

    if notes_col:
        out["notes"] = df[colmap["notes"]].astype(str).str.strip()
    else:
        out["notes"] = ""

    mask_valid = out["dye_base_code"].str.len() > 0
    dropped = len(out) - int(mask_valid.sum())
    if dropped:
        warnings.append(f"Dropped {dropped} row(s) with empty dye_base_code.")
    out = out[mask_valid].reset_index(drop=True)

    return out, warnings


def load_dyes_from_csv(csv_path: str | Path, engine: Optional[Engine] = None) -> dict:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Dye CSV not found: {path}")

    df_raw = _load_csv_normalized(path)
    df, warnings = _normalize_dye_columns(df_raw)

    if df.empty:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": warnings}

    if engine is None:
        engine = get_engine_from_env()

    unique_codes = df["dye_base_code"].unique().tolist()

    with engine.begin() as cx:
        existing_codes = set(
            cx.execute(
                text(
                    """
                    SELECT dye_base_code
                    FROM public.dyes
                    WHERE dye_base_code = ANY(:codes)
                    """
                ),
                {"codes": unique_codes},
            ).scalars().all()
        )

    sql = text(
        """
        INSERT INTO public.dyes
          (dye_base_code, name, notes)
        VALUES
          (:base_code, NULLIF(:name, ''), NULLIF(:notes, ''))
        ON CONFLICT (dye_base_code) DO UPDATE
        SET name  = EXCLUDED.name,
            notes = EXCLUDED.notes
        """
    )

    inserted = 0
    updated = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            base_code = row["dye_base_code"]
            params = {
                "base_code": base_code,
                "name": row.get("name", "") or "",
                "notes": row.get("notes", "") or "",
            }
            cx.execute(sql, params)
            if base_code in existing_codes:
                updated += 1
            else:
                inserted += 1
                existing_codes.add(base_code)

    return {"rows": len(df), "inserted": inserted, "updated": updated, "warnings": warnings}

# ---------------------------------------------------------------------------
# Fish (standard) — load into public.fish_instance from fish.xlsx
# ---------------------------------------------------------------------------

def _make_fish_code() -> str:
    """
    Generate a fish_code like FSH-XXXXXXXX using a random UUID and base36.
    Deterministic across a single run, but not across rebuilds — intended
    for fresh v7 loads where DB is wiped before seeding.
    """
    import uuid as _uuid  # local import to avoid touching module-level imports

    n = _uuid.uuid4().int & ((1 << 40) - 1)
    alpha = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = []
    for _ in range(8):
        out.append(alpha[n % 36])
        n //= 36
    return "FSH-" + "".join(reversed(out))


def _normalize_fish_standard(df: pd.DataFrame) -> Tuple[pd.DataFrame, list[str]]:
    """
    Normalize the standard fish.xlsx sheet into canonical columns for v7.

    Input columns (as seen from your sheet):
      - birthday
      - genetic_background
      - nickname
      - line_building_stage
      - transgene_base_code
      - allele_nickname
      - zygosity
      - created_by
      - description

    For now we only use the scalar fish fields to populate public.fish_instance:
      - birthday            -> birthday (parsed date)
      - genetic_background  -> genetic_background
      - line_building_stage -> line_building_stage
      - nickname            -> nickname
      - description         -> notes

    Genotype fields (transgene_base_code, allele_nickname, zygosity) are retained
    in the DataFrame for possible future use but are not written to the DB yet.
    """
    warnings: list[str] = []
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Required-ish columns
    required_cols = ["birthday", "nickname"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Fish sheet is missing required columns: {missing}")

    # Parse birthday to date
    def _parse_date(x):
        if pd.isna(x) or x == "":
            return None
        try:
            # pandas Timestamp -> date
            if isinstance(x, pd.Timestamp):
                return x.date()
            # string
            return pd.to_datetime(str(x)).date()
        except Exception:
            return None

    df["birthday"] = df["birthday"].apply(_parse_date)
    bad_dates = df["birthday"].isna().sum()
    if bad_dates:
        warnings.append(f"{bad_dates} row(s) have invalid or missing birthday and will be dropped.")
    df = df[df["birthday"].notna()].reset_index(drop=True)

    # Scalar fields
    out = pd.DataFrame()
    out["birthday"] = df["birthday"]
    out["genetic_background"] = df.get("genetic_background", "").astype(str).str.strip()
    out["line_building_stage"] = df.get("line_building_stage", "").astype(str).str.strip()
    out["nickname"] = df.get("nickname", "").astype(str).str.strip()
    out["notes"] = df.get("description", "").astype(str).str.strip()

    # Keep genotype-related fields for potential later use
    out["transgene_base_code"] = df.get("transgene_base_code", "").astype(str).str.strip()
    out["allele_nickname"] = df.get("allele_nickname", "").astype(str).str.strip()
    out["zygosity"] = df.get("zygosity", "").astype(str).str.strip()
    out["created_by"] = df.get("created_by", "").astype(str).str.strip()

    # Drop rows with empty nickname (optional; log if any)
    mask_nick = out["nickname"].str.len() > 0
    dropped_nick = len(out) - int(mask_nick.sum())
    if dropped_nick:
        warnings.append(f"{dropped_nick} row(s) have empty nickname and will be dropped.")
    out = out[mask_nick].reset_index(drop=True)

    return out, warnings


def load_fish_standard_from_excel(xlsx_path: str | Path, engine: Optional[Engine] = None) -> dict:
    """
    Load standard fish instances from fish.xlsx into public.fish_instance.

    Behavior:
      - Reads the first sheet from the given Excel file.
      - Normalizes columns with _normalize_fish_standard.
      - Inserts rows into public.fish_instance with:
          fish_code (random slug),
          birthday,
          genetic_background,
          line_building_stage,
          nickname,
          notes.
      - Does NOT currently populate genotypes or join tables; those can be
        wired in a follow-up pass using the transgene_base_code / allele_nickname
        columns that are preserved in the normalized DataFrame.
      - Insert-only (no upsert). Intended to be run on a fresh v7 DB after rebuild.
    """
    from pathlib import Path as _Path
    import pandas as _pd

    path = _Path(xlsx_path)
    if not path.exists():
        raise FileNotFoundError(f"Fish Excel file not found: {path}")

    # Read the first sheet; adjust if you ever add multiple sheets.
    df_raw = _pd.read_excel(path)
    df, warnings = _normalize_fish_standard(df_raw)

    if df.empty:
        return {"rows": 0, "inserted": 0, "warnings": warnings}

    if engine is None:
        engine = get_engine_from_env()

    sql = text(
        """
        INSERT INTO public.fish_instance
          (fish_code, fish_group_id, birthday, genetic_background,
           line_building_stage, nickname, notes)
        VALUES
          (:fish_code, NULL, :birthday, NULLIF(:bg, ''), NULLIF(:stage, ''), NULLIF(:nick, ''), NULLIF(:notes, ''))
        """
    )

    inserted = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            fish_code = _make_fish_code()
            params = {
                "fish_code": fish_code,
                "birthday": row["birthday"],
                "bg": row.get("genetic_background", "") or "",
                "stage": row.get("line_building_stage", "") or "",
                "nick": row.get("nickname", "") or "",
                "notes": row.get("notes", "") or "",
            }
            cx.execute(sql, params)
            inserted += 1

    return {"rows": len(df), "inserted": inserted, "warnings": warnings}

# ---------------------------------------------------------------------------
# Fluors / Tags / Fusions from standard seed kit
# ---------------------------------------------------------------------------

def _build_alias_maps(alias_csv: Optional[Path]) -> dict:
    """
    Read alias.csv and return dicts for fluors/tags keyed by lowercase target_key.

    alias.csv columns:
      - target_kind (e.g. 'fluor', 'tag')
      - target_key  (canonical code, e.g. 'mStayGold')
      - alias       (alternate spelling, e.g. 'mSG')
    """
    maps: dict[str, dict[str, list[str]]] = {
        "fluor": {},
        "tag": {},
    }
    if not alias_csv:
        return maps

    import pandas as _pd

    df = _pd.read_csv(alias_csv)
    if df.empty:
        return maps

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in ["target_kind", "target_key", "alias"]:
        if col not in df.columns:
            return maps

    df = df.dropna(subset=["target_kind", "target_key", "alias"])
    df["target_kind"] = df["target_kind"].astype(str).str.strip().str.lower()
    df["target_key"] = df["target_key"].astype(str).str.strip()
    df["alias"] = df["alias"].astype(str).str.strip()

    for _, row in df.iterrows():
        kind = row["target_kind"]
        key = row["target_key"]
        alias = row["alias"]
        if not alias:
            continue
        if kind in maps:
            m = maps[kind]
            lk = key.lower()
            if lk not in m:
                m[lk] = []
            if alias not in m[lk]:
                m[lk].append(alias)

    return maps


def load_fluors_from_csv(
    fluors_csv: str | Path,
    alias_csv: Optional[str | Path] = None,
    engine: Optional[Engine] = None,
) -> dict:
    """
    Load or upsert fluors into public.fluors from standard fluors.csv.

    fluors.csv columns:
      - nickname
      - aliases
      - excitation_nm
      - emission_nm
      - notes

    public.fluors columns:
      - id uuid
      - fluor_code text
      - fluor_name text
      - excitation_nm integer
      - emission_nm integer
      - alt_names text[]
      - notes text
      - created_at timestamptz

    Upserts by fluor_code (case-insensitive).
    """
    from pathlib import Path as _Path
    import pandas as _pd

    fpath = _Path(fluors_csv)
    if not fpath.exists():
        raise FileNotFoundError(f"Fluors CSV not found: {fpath}")

    df = _pd.read_csv(fpath)
    if df.empty:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": []}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["nickname"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"fluors.csv is missing required columns: {missing}")

    df["nickname"] = df["nickname"].astype(str).str.strip()
    df["aliases"] = df.get("aliases", "").astype(str)
    df["excitation_nm"] = df.get("excitation_nm")
    df["emission_nm"] = df.get("emission_nm")
    df["notes"] = df.get("notes", "").astype(str)

    alias_maps = _build_alias_maps(_Path(alias_csv) if alias_csv else None)
    fluor_alias_map = alias_maps.get("fluor", {})

    records = []
    warnings: list[str] = []

    for _, row in df.iterrows():
        code = row["nickname"]
        if not code:
            continue
        key_l = code.lower()
        alt: list[str] = []

        raw_aliases = str(row.get("aliases", "") or "")
        for part in raw_aliases.replace(";", ",").split(","):
            a = part.strip()
            if a:
                alt.append(a)

        extra = fluor_alias_map.get(key_l, [])
        for a in extra:
            if a not in alt:
                alt.append(a)

        try:
            ex_nm = int(row["excitation_nm"]) if not _pd.isna(row["excitation_nm"]) else None
        except Exception:
            ex_nm = None
            warnings.append(f"Invalid excitation_nm for fluor {code!r}, storing NULL.")

        try:
            em_nm = int(row["emission_nm"]) if not _pd.isna(row["emission_nm"]) else None
        except Exception:
            em_nm = None
            warnings.append(f"Invalid emission_nm for fluor {code!r}, storing NULL.")

        notes = row.get("notes", "") or ""

        records.append(
            {
                "fluor_code": code,
                "fluor_name": code,
                "excitation_nm": ex_nm,
                "emission_nm": em_nm,
                "alt_names": alt,
                "notes": notes.strip(),
            }
        )

    if not records:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": warnings}

    if engine is None:
        engine = get_engine_from_env()

    import itertools

    sql = text(
        """
        INSERT INTO public.fluors
          (fluor_code, fluor_name, excitation_nm, emission_nm, alt_names, notes)
        VALUES
          (:code, NULLIF(:name,''), :ex_nm, :em_nm, :alt_names, NULLIF(:notes,''))
        ON CONFLICT (fluor_code) DO UPDATE
        SET fluor_name    = EXCLUDED.fluor_name,
            excitation_nm = EXCLUDED.excitation_nm,
            emission_nm   = EXCLUDED.emission_nm,
            alt_names     = EXCLUDED.alt_names,
            notes         = EXCLUDED.notes
        """
    )

    codes = {r["fluor_code"] for r in records}
    with engine.begin() as cx:
        existing = set(
            cx.execute(
                text(
                    "SELECT fluor_code FROM public.fluors WHERE lower(fluor_code) = ANY(:codes)"
                ),
                {"codes": [c.lower() for c in codes]},
            ).scalars().all()
        )

    inserted = 0
    updated = 0
    with engine.begin() as cx:
        for r in records:
            code = r["fluor_code"]
            params = {
                "code": code,
                "name": r["fluor_name"],
                "ex_nm": r["excitation_nm"],
                "em_nm": r["emission_nm"],
                "alt_names": r["alt_names"] if r["alt_names"] else None,
                "notes": r["notes"],
            }
            cx.execute(sql, params)
            if code in existing:
                updated += 1
            else:
                inserted += 1
                existing.add(code)

    return {"rows": len(records), "inserted": inserted, "updated": updated, "warnings": warnings}


def load_tags_from_excel(
    tags_xlsx: str | Path,
    alias_csv: Optional[str | Path] = None,
    engine: Optional[Engine] = None,
) -> dict:
    """
    Load or upsert tags into public.tags from tags.xlsx.

    tags.xlsx columns:
      - nickname
      - aliases
      - localization
      - note
      - citation_link

    public.tags columns:
      - id uuid
      - tag_code text
      - tag_name text
      - alt_names text[]
      - localization text
      - notes text
      - created_at timestamptz

    Upserts by tag_code.
    """
    from pathlib import Path as _Path
    import pandas as _pd

    tpath = _Path(tags_xlsx)
    if not tpath.exists():
        raise FileNotFoundError(f"Tags Excel file not found: {tpath}")

    df = _pd.read_excel(tpath)
    if df.empty:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": []}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["nickname"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"tags.xlsx is missing required columns: {missing}")

    df["nickname"] = df["nickname"].astype(str).str.strip()
    df["aliases"] = df.get("aliases", "").astype(str)
    df["localization"] = df.get("localization", "").astype(str)
    df["note"] = df.get("note", "").astype(str)
    df["citation_link"] = df.get("citation_link", "").astype(str)

    alias_maps = _build_alias_maps(_Path(alias_csv) if alias_csv else None)
    tag_alias_map = alias_maps.get("tag", {})

    records = []
    warnings: list[str] = []

    for _, row in df.iterrows():
        code = row["nickname"]
        if not code:
            continue
        key_l = code.lower()

        alt: list[str] = []
        raw_aliases = str(row.get("aliases", "") or "")
        for part in raw_aliases.replace(";", ",").split(","):
            a = part.strip()
            if a:
                alt.append(a)

        extra = tag_alias_map.get(key_l, [])
        for a in extra:
            if a not in alt:
                alt.append(a)

        loc = row.get("localization", "") or ""
        note = row.get("note", "") or ""
        citation = row.get("citation_link", "") or ""
        notes = note.strip()
        if citation and citation.strip():
            if notes:
                notes = f"{notes} [citation: {citation.strip()}]"
            else:
                notes = f"[citation: {citation.strip()}]"

        records.append(
            {
                "tag_code": code,
                "tag_name": code,
                "alt_names": alt,
                "localization": loc.strip(),
                "notes": notes,
            }
        )

    if not records:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": warnings}

    if engine is None:
        engine = get_engine_from_env()

    sql = text(
        """
        INSERT INTO public.tags
          (tag_code, tag_name, alt_names, localization, notes)
        VALUES
          (:code, NULLIF(:name,''), :alt_names, NULLIF(:loc,''), NULLIF(:notes,''))
        ON CONFLICT (tag_code) DO UPDATE
        SET tag_name    = EXCLUDED.tag_name,
            alt_names   = EXCLUDED.alt_names,
            localization = EXCLUDED.localization,
            notes       = EXCLUDED.notes
        """
    )

    codes = {r["tag_code"] for r in records}
    with engine.begin() as cx:
        existing = set(
            cx.execute(
                text(
                    "SELECT tag_code FROM public.tags WHERE lower(tag_code) = ANY(:codes)"
                ),
                {"codes": [c.lower() for c in codes]},
            ).scalars().all()
        )

    inserted = 0
    updated = 0
    with engine.begin() as cx:
        for r in records:
            code = r["tag_code"]
            params = {
                "code": code,
                "name": r["tag_name"],
                "alt_names": r["alt_names"] if r["alt_names"] else None,
                "loc": r["localization"],
                "notes": r["notes"],
            }
            cx.execute(sql, params)
            if code in existing:
                updated += 1
            else:
                inserted += 1
                existing.add(code)

    return {"rows": len(records), "inserted": inserted, "updated": updated, "warnings": warnings}

def _resolve_fluor_id(cx, name: str) -> Optional[str]:
    """
    Resolve a fluor identifier (canonical or alias) to a fluor.id.
    """
    if not name:
        return None
    name_s = str(name).strip()
    if not name_s:
        return None
    row = cx.execute(
        text(
            """
            SELECT id
            FROM public.fluors
            WHERE lower(fluor_code) = lower(:n)
               OR EXISTS (
                    SELECT 1 FROM unnest(alt_names) a WHERE lower(a) = lower(:n)
                 )
            LIMIT 1
            """
        ),
        {"n": name_s},
    ).scalar()
    return row


def _resolve_tag_id(cx, name: Optional[str]) -> Optional[str]:
    """
    Resolve a tag identifier (canonical or alias) to tags.id.
    """
    if not name:
        return None
    name_s = str(name).strip()
    if not name_s:
        return None
    row = cx.execute(
        text(
            """
            SELECT id
            FROM public.tags
            WHERE lower(tag_code) = lower(:n)
               OR EXISTS (
                    SELECT 1 FROM unnest(alt_names) a WHERE lower(a) = lower(:n)
                 )
            LIMIT 1
            """
        ),
        {"n": name_s},
    ).scalar()
    return row


def _clean_tag_pos(raw, warnings: list[str], context: str) -> Optional[str]:
    """
    Normalize tag_pos for fusions to satisfy ck_fusions_tag_pos.

    Valid:
      - 'N' or 'C' (any case)
    Everything else (including NaN, empty, weird strings) -> None, with optional warning.
    """
    s = str(raw or "").strip()
    if not s or s.lower() == "nan":
        return None
    u = s.upper()
    if u in ("N", "C"):
        return u
    warnings.append(f"Unknown tag_pos {s!r} for {context}; storing NULL.")
    return None


def _get_or_create_fusion(
    cx,
    fluor_id: str,
    tag_id: Optional[str],
    tag_pos: Optional[str],
):
    """
    Find or create a fusion row for (fluor_id, tag_id, tag_pos) and return its id.
    """
    params = {
        "fluor_id": fluor_id,
        "tag_id": tag_id,
        "tag_pos": tag_pos,
    }

    row = cx.execute(
        text(
            """
            SELECT id
            FROM public.fusions
            WHERE fluor_id = :fluor_id
              AND (
                    (:tag_id IS NULL AND tag_id IS NULL)
                 OR (tag_id = :tag_id)
              )
              AND COALESCE(tag_pos,'') = COALESCE(:tag_pos,'')
            LIMIT 1
            """
        ),
        params,
    ).scalar()

    if row:
        return row

    fid = cx.execute(
        text(
            """
            INSERT INTO public.fusions (fluor_id, tag_id, tag_pos)
            VALUES (:fluor_id, :tag_id, :tag_pos)
            RETURNING id
            """
        ),
        params,
    ).scalar()

    return fid


def load_plasmid_fusions_from_csv(
    plasmid_fusions_csv: str | Path,
    engine: Optional[Engine] = None,
) -> dict:
    """
    Load plasmid_fusions.csv into public.fusions + join_plasmid_fusions.

    plasmid_fusions.csv columns:
      - plasmid_base_code
      - nickname
      - n_fluors_per_plasmid
      - fluor
      - tag
      - tag_pos
    """
    from pathlib import Path as _Path
    import pandas as _pd

    fpath = _Path(plasmid_fusions_csv)
    if not fpath.exists():
        raise FileNotFoundError(f"plasmid_fusions CSV not found: {fpath}")

    df = _pd.read_csv(fpath)
    if df.empty:
        return {"rows": 0, "fusions_created": 0, "links_created": 0, "warnings": []}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["plasmid_base_code", "fluor"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"plasmid_fusions.csv is missing required columns: {missing}")

    df["plasmid_base_code"] = df["plasmid_base_code"].astype(str).str.strip()
    df["fluor"] = df["fluor"].astype(str)
    df["tag"] = df.get("tag", "").astype(str)
    df["tag_pos"] = df.get("tag_pos", "")

    if engine is None:
        engine = get_engine_from_env()

    warnings: list[str] = []
    fusions_created = 0
    links_created = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            base = normalize_base_code(row["plasmid_base_code"])
            if not base:
                continue

            plasmid_id = cx.execute(
                text(
                    "SELECT id FROM public.plasmids WHERE plasmid_base_code = :b LIMIT 1"
                ),
                {"b": base},
            ).scalar()
            if not plasmid_id:
                warnings.append(f"Skipping plasmid_fusion row: plasmid_base_code {base!r} not found.")
                continue

            fluor_name = row.get("fluor", "") or ""
            fluor_id = _resolve_fluor_id(cx, fluor_name)
            if not fluor_id:
                warnings.append(f"Skipping plasmid_fusion row: fluor {fluor_name!r} not found.")
                continue

            tag_name = row.get("tag")
            tag_id = _resolve_tag_id(cx, tag_name)
            raw_pos = row.get("tag_pos")
            tag_pos = _clean_tag_pos(
                raw_pos,
                warnings,
                f"plasmid_base_code={base}, fluor={fluor_name}, tag={tag_name}",
            )

            fusion_id = _get_or_create_fusion(cx, fluor_id, tag_id, tag_pos)
            if not fusion_id:
                warnings.append(
                    f"Failed to create or find fusion for plasmid={base}, fluor={fluor_name}, tag={tag_name}, tag_pos={raw_pos!r}."
                )
                continue

            res = cx.execute(
                text(
                    """
                    INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id)
                    VALUES (:pid, :fid)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"pid": plasmid_id, "fid": fusion_id},
            )
            if res.rowcount and res.rowcount > 0:
                links_created += 1

    return {
        "rows": len(df),
        "fusions_created": fusions_created,
        "links_created": links_created,
        "warnings": warnings,
    }


def load_rna_fusions_from_csv(
    rna_fusions_csv: str | Path,
    engine: Optional[Engine] = None,
) -> dict:
    """
    Load rna_fusions.csv into public.fusions + join_rna_fusions.

    rna_fusions.csv columns:
      - rna_base_code (e.g. 'RNA(MGCO-01)')
      - nickname
      - n_fluors_per_rna
      - fluor
      - tag
      - tag_pos
      - token
    """
    from pathlib import Path as _Path
    import pandas as _pd

    rpath = _Path(rna_fusions_csv)
    if not rpath.exists():
        raise FileNotFoundError(f"rna_fusions CSV not found: {rpath}")

    df = _pd.read_csv(rpath)
    if df.empty:
        return {"rows": 0, "fusions_created": 0, "links_created": 0, "warnings": []}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["rna_base_code", "fluor"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"rna_fusions.csv is missing required columns: {missing}")

    df["rna_base_code"] = df["rna_base_code"].astype(str).str.strip()
    df["fluor"] = df.get("fluor", "").astype(str)
    df["tag"] = df.get("tag", "").astype(str)
    df["tag_pos"] = df.get("tag_pos", "")

    def _extract_rna_base(raw: str) -> str:
        s = str(raw or "").strip()
        if s.upper().startswith("RNA(") and s.endswith(")"):
            inner = s[4:-1]
        else:
            inner = s
        return normalize_base_code(inner)

    df["rna_base_code_norm"] = df["rna_base_code"].apply(_extract_rna_base)

    if engine is None:
        engine = get_engine_from_env()

    warnings: list[str] = []
    fusions_created = 0
    links_created = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            base = row["rna_base_code_norm"]
            if not base:
                continue

            rna_id = cx.execute(
                text(
                    "SELECT id FROM public.rnas WHERE rna_base_code = :b LIMIT 1"
                ),
                {"b": base},
            ).scalar()
            if not rna_id:
                warnings.append(f"Skipping rna_fusion row: rna_base_code {base!r} not found.")
                continue

            fluor_name = row.get("fluor", "") or ""
            fluor_id = _resolve_fluor_id(cx, fluor_name)
            if not fluor_id:
                warnings.append(f"Skipping rna_fusion row: fluor {fluor_name!r} not found.")
                continue

            tag_name = row.get("tag")
            tag_id = _resolve_tag_id(cx, tag_name)
            raw_pos = row.get("tag_pos")
            tag_pos = _clean_tag_pos(
                raw_pos,
                warnings,
                f"rna_base_code={base}, fluor={fluor_name}, tag={tag_name}",
            )

            fusion_id = _get