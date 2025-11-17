from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.util import get_engine_from_env

def _make_fish_code() -> str:
    import uuid as _uuid
    n = _uuid.uuid4().int & ((1 << 40) - 1)
    alpha = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = []
    for _ in range(8):
        out.append(alpha[n % 36])
        n //= 36
    return "FSH-" + "".join(reversed(out))

def _normalize_fish_standard(df: pd.DataFrame) -> Tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required_cols = ["birthday", "nickname"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Fish sheet is missing required columns: {missing}")

    def _parse_date(x):
        if pd.isna(x) or x == "":
            return None
        try:
            if isinstance(x, pd.Timestamp):
                return x.date()
            return pd.to_datetime(str(x)).date()
        except Exception:
            return None

    df["birthday"] = df["birthday"].apply(_parse_date)
    bad_dates = df["birthday"].isna().sum()
    if bad_dates:
        warnings.append(f"{bad_dates} row(s) have invalid or missing birthday and will be dropped.")
    df = df[df["birthday"].notna()].reset_index(drop=True)

    out = pd.DataFrame()
    out["birthday"] = df["birthday"]
    out["genetic_background"] = df.get("genetic_background", "").astype(str).str.strip()
    out["line_building_stage"] = df.get("line_building_stage", "").astype(str).str.strip()
    out["nickname"] = df.get("nickname", "").astype(str).str.strip()
    out["notes"] = df.get("description", "").astype(str).str.strip()

    out["transgene_base_code"] = df.get("transgene_base_code", "").astype(str).str.strip()
    out["allele_nickname"] = df.get("allele_nickname", "").astype(str).str.strip()
    out["zygosity"] = df.get("zygosity", "").astype(str).str.strip()
    out["created_by"] = df.get("created_by", "").astype(str).str.strip()

    mask_nick = out["nickname"].str.len() > 0
    dropped_nick = len(out) - int(mask_nick.sum())
    if dropped_nick:
        warnings.append(f"{dropped_nick} row(s) have empty nickname and will be dropped.")
    out = out[mask_nick].reset_index(drop=True)

    return out, warnings

def load_fish_standard_from_excel(xlsx_path: str | Path, engine: Optional[Engine] = None) -> dict:
    from pathlib import Path as _Path
    import pandas as _pd

    path = _Path(xlsx_path)
    if not path.exists():
        raise FileNotFoundError(f"Fish Excel file not found: {path}")

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
