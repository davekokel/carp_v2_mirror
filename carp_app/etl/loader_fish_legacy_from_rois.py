from __future__ import annotations

from pathlib import Path
from typing import Optional, List

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.loaders import get_engine_from_env


def _norm_str(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _norm_date(v):
    if pd.isna(v) or v is None or str(v).strip() == "":
        return None
    if isinstance(v, pd.Timestamp):
        return v.date()
    s = str(v).strip()
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None


def load_legacy_fish_from_rois(
    csv_path: str | Path,
    engine: Optional[Engine] = None,
) -> dict:
    """
    Load legacy fish instances (FSH_LEGACY_...) into public.fish_instance
    from fish_instances_standard_from_legacy.csv.

    Columns expected:
      - fish_code
      - birthday
      - genetic_background
      - line_building_stage
      - nickname
      - notes
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"legacy fish CSV not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        return {"rows": 0, "fish_inserted": 0, "skipped_existing": 0, "warnings": []}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["fish_code", "birthday", "nickname"]
    missing = [c for c in required if c not in df.columns]
    warnings: List[str] = []
    if missing:
        warnings.append(f"legacy fish CSV missing required columns: {missing}")

    for col in ["fish_code", "genetic_background", "line_building_stage", "nickname", "notes"]:
        if col in df.columns:
            df[col] = df[col].apply(_norm_str)
        else:
            df[col] = ""

    df["birthday"] = df["birthday"].apply(_norm_date)

    if engine is None:
        engine = get_engine_from_env()

    fish_inserted = 0
    skipped_existing = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            code = row.get("fish_code", "") or ""
            if not code:
                warnings.append("Skipping legacy fish row with empty fish_code")
                continue

            existing = cx.execute(
                text(
                    """
                    SELECT 1
                    FROM public.fish_instance
                    WHERE fish_code = :code
                    LIMIT 1
                    """
                ),
                {"code": code},
            ).scalar()

            if existing:
                skipped_existing += 1
                continue

            bday = row["birthday"]
            bg = row.get("genetic_background", "") or ""
            stage = row.get("line_building_stage", "") or ""
            nick = row.get("nickname", "") or ""
            notes = row.get("notes", "") or ""

            cx.execute(
                text(
                    """
                    INSERT INTO public.fish_instance
                      (id, fish_code, fish_group_id, birthday, genetic_background, line_building_stage, nickname, notes)
                    SELECT
                      gen_random_uuid(),
                      :code,
                      NULL,
                      :bday,
                      NULLIF(:bg,''),
                      NULLIF(:stage,''),
                      NULLIF(:nick,''),
                      NULLIF(:notes,'')
                    """
                ),
                {
                    "code": code,
                    "bday": bday,
                    "bg": bg,
                    "stage": stage,
                    "nick": nick,
                    "notes": notes,
                },
            )
            fish_inserted += 1

    return {
        "rows": len(df),
        "fish_inserted": fish_inserted,
        "skipped_existing": skipped_existing,
        "warnings": warnings,
    }
