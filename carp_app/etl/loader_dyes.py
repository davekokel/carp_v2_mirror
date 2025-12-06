from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.util import (
    get_engine_from_env,
    normalize_base_code,
    _load_csv_normalized,
)


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
    """v11: Load / upsert dyes into public.dyes using nickname/display_name.

    CSV still uses columns: dye_base_code, name, notes.
    We map:
      dye_base_code -> dyes.nickname
      name          -> dyes.display_name
    """
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

    # existing dyes keyed by nickname
    with engine.begin() as cx:
        existing_codes = set(
            cx.execute(
                text(
                    """
                    SELECT nickname
                    FROM public.dyes
                    WHERE nickname = ANY(:codes)
                    """
                ),
                {"codes": unique_codes},
            ).scalars().all()
        )

    sql = text(
        """
        INSERT INTO public.dyes
          (nickname, display_name, notes)
        VALUES
          (:nickname, NULLIF(:display_name, ''), NULLIF(:notes, ''))
        ON CONFLICT (nickname) DO UPDATE
        SET display_name = EXCLUDED.display_name,
            notes        = EXCLUDED.notes
        """
    )

    inserted = 0
    updated = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            base_code = row["dye_base_code"]
            params = {
                "nickname": base_code,
                "display_name": row.get("name", "") or "",
                "notes": row.get("notes", "") or "",
            }
            cx.execute(sql, params)
            if base_code in existing_codes:
                updated += 1
            else:
                inserted += 1
                existing_codes.add(base_code)

    return {"rows": len(df), "inserted": inserted, "updated": updated, "warnings": warnings}


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Load / upsert dyes into public.dyes from a CSV file."
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to dyes CSV (e.g. seed_kits/.../dyes.csv)",
    )
    args = parser.parse_args(argv)

    engine = get_engine_from_env()
    print(f"DB_URL={engine.url}")

    result = load_dyes_from_csv(args.csv, engine=engine)

    for w in result.get("warnings", []):
        print(f"[dyes] WARN: {w}")
    print(
        f"[dyes] rows={result['rows']} "
        f"inserted={result['inserted']} "
        f"updated={result['updated']}"
    )


if __name__ == "__main__":
    main()

# ───────────────────────────────────────────────────────
# v11 PATCH: override load_dyes_from_csv to use nickname/display_name
# ───────────────────────────────────────────────────────
def load_dyes_from_csv(csv_path: str | Path, engine: Optional[Engine] = None) -> dict:
    """
    v11: Load / upsert dyes into public.dyes.
    CSV is expected to have columns: dye_base_code, name, notes (same as before),
    but we now map:
      dye_base_code -> nickname
      name          -> display_name
    """
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

    # existing dyes by nickname
    with engine.begin() as cx:
        existing_codes = set(
            cx.execute(
                text(
                    """
                    SELECT nickname
                    FROM public.dyes
                    WHERE nickname = ANY(:codes)
                    """
                ),
                {"codes": unique_codes},
            ).scalars().all()
        )

    sql = text(
        """
        INSERT INTO public.dyes
          (nickname, display_name, notes)
        VALUES
          (:nickname, NULLIF(:display_name, ''), NULLIF(:notes, ''))
        ON CONFLICT (nickname) DO UPDATE
        SET display_name = EXCLUDED.display_name,
            notes        = EXCLUDED.notes
        """
    )

    inserted = 0
    updated = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            base_code = row["dye_base_code"]
            params = {
                "nickname": base_code,
                "display_name": row.get("name", "") or "",
                "notes": row.get("notes", "") or "",
            }
            cx.execute(sql, params)
            if base_code in existing_codes:
                updated += 1
            else:
                inserted += 1
                existing_codes.add(base_code)

    return {"rows": len(df), "inserted": inserted, "updated": updated, "warnings": warnings}

