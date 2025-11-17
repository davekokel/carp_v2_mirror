from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.util import get_engine_from_env, normalize_base_code, _load_csv_normalized

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
