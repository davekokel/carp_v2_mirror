from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.util import get_engine_from_env, normalize_base_code, _load_csv_normalized

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
