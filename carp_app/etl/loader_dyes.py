from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.util import get_engine_from_env, normalize_base_code, _load_csv_normalized

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
