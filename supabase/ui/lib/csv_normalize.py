# supabase/ui/lib/csv_normalize.py
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from datetime import UTC, datetime

import pandas as pd


def _pick(df: pd.DataFrame, names: List[str]) -> pd.Series:
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([None] * len(df))


def normalize_fish_seedkit(df_in: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the seedkit CSV to our canonical schema:

    Required intent:
      - fish_code (or auto-generate)
      - transgene_base_code
      - allele_nickname  (preferred) OR allele_number (legacy)
    Optional:
      - name, created_by, date_birth/date_of_birth/birth_date, zygosity

    Output columns (all present):
      ['fish_code','transgene_base_code','allele_nickname','allele_number',
       'name','created_by','date_birth','zygosity']
    """
    df = df_in.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    out = pd.DataFrame()
    out["fish_code"]           = _pick(df, ["fish_code", "code", "fish id", "id"]).astype("string")
    out["transgene_base_code"] = _pick(df, ["transgene_base_code"]).astype("string")
    out["allele_nickname"]     = _pick(df, ["allele_nickname"]).astype("string")
    out["name"]                = _pick(df, ["name", "fish_name"]).astype("string")
    out["created_by"]          = _pick(df, ["created_by", "user", "owner"]).astype("string")
    out["zygosity"]            = _pick(df, ["zygosity"]).astype("string")

    # accept either date_birth or date_of_birth; normalize to date_birth
    dob_any = _pick(df, ["date_birth", "date_of_birth", "birth_date"])
    try:
        out["date_birth"] = pd.to_datetime(dob_any, errors="coerce").dt.date
    except Exception:
        out["date_birth"] = None

    # numeric allele number only if explicitly provided (legacy support)
    if "allele_number" in df.columns:
        out["allele_number"] = pd.to_numeric(df["allele_number"], errors="coerce").astype("Int64")
    else:
        out["allele_number"] = pd.Series([pd.NA] * len(out), dtype="Int64")

    # Autogenerate fish_code if missing
    mask = out["fish_code"].isna() | (out["fish_code"].astype(str).str.strip() == "")
    if mask.any():
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        out.loc[mask, "fish_code"] = [f"FSH-{stamp}-{i:03d}" for i in range(1, int(mask.sum()) + 1)]

    # ensure all expected columns exist
    for col in [
        "fish_code", "transgene_base_code", "allele_nickname", "allele_number",
        "name", "created_by", "date_birth", "zygosity"
    ]:
        if col not in out.columns:
            out[col] = pd.NA

    return out[[
        "fish_code", "transgene_base_code", "allele_nickname", "allele_number",
        "name", "created_by", "date_birth", "zygosity"
    ]]


def validate_seedkit(df_norm: pd.DataFrame) -> List[str]:
    """
    Lightweight validations; returns a list of human-readable issues.
    """
    issues: List[str] = []

    if df_norm.empty:
        issues.append("CSV appears empty after normalization.")
        return issues

    # must have base+nickname OR (legacy) number in at least one row
    base_nonempty = df_norm["transgene_base_code"].astype("string").str.strip().ne("")
    nick_nonempty = df_norm["allele_nickname"].astype("string").str.strip().ne("")
    has_num       = df_norm["allele_number"].notna()

    if not (base_nonempty & (nick_nonempty | has_num)).any():
        issues.append("No rows contain a valid (transgene_base_code + allele_nickname) or legacy allele_number.")

    # warn on blanks that will be auto-generated
    if (df_norm["fish_code"].astype("string").str.strip() == "").any():
        issues.append("Some fish_code were blank and will be auto-generated.")

    # optional: surface duplicated fish_code
    dup_codes = df_norm["fish_code"].value_counts(dropna=False)
    dups = dup_codes[dup_codes > 1]
    if not dups.empty:
        issues.append(f"Duplicate fish_code in file: {', '.join(map(str, dups.index.tolist()))}")

    return issues