from __future__ import annotations

from pathlib import Path
from typing import Optional, List

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.loaders import get_engine_from_env, normalize_base_code


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


def load_fish_standard_from_xlsx(
    xlsx_path: str | Path,
    engine: Optional[Engine] = None,
) -> dict:
    path = Path(xlsx_path)
    if not path.exists():
        raise FileNotFoundError(f"fish.xlsx not found at: {path}")

    df = pd.read_excel(path)
    if df.empty:
        return {
            "rows": 0,
            "fish_inserted": 0,
            "allele_links": 0,
            "warnings": ["fish.xlsx is empty"],
        }

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = [
        "birthday",
        "genetic_background",
        "nickname",
        "line_building_stage",
        "transgene_base_code",
        "allele_nickname",
        "zygosity",
    ]
    missing = [c for c in required if c not in df.columns]
    warnings: List[str] = []
    if missing:
        warnings.append(f"fish.xlsx missing required columns: {missing}")

    for col in ["genetic_background", "nickname", "line_building_stage", "transgene_base_code", "allele_nickname", "zygosity", "description"]:
        if col in df.columns:
            df[col] = df[col].apply(_norm_str)
        else:
            df[col] = ""

    df["birthday"] = df["birthday"].apply(_norm_date)

    if engine is None:
        engine = get_engine_from_env()

    fish_inserted = 0
    allele_links = 0

    with engine.begin() as cx:
        cx.execute(
            text(
                """
                TRUNCATE TABLE
                  public.join_fish_transgene_alleles,
                  public.fish_instance
                RESTART IDENTITY CASCADE;
                """
            )
        )

        for _, row in df.iterrows():
            bday = row["birthday"]
            bg = row.get("genetic_background", "") or ""
            stage = row.get("line_building_stage", "") or ""
            nick = row.get("nickname", "") or ""
            notes = row.get("description", "") or ""

            fish_row = cx.execute(
                text(
                    """
                    WITH new_id AS (
                      SELECT gen_random_uuid() AS id
                    )
                    INSERT INTO public.fish_instance
                      (id, fish_code, fish_group_id, birthday, genetic_background, line_building_stage, nickname, notes)
                    SELECT
                      nid.id,
                      'FSH-' || left(nid.id::text, 8),
                      NULL,
                      :bday,
                      NULLIF(:bg,''),
                      NULLIF(:stage,''),
                      NULLIF(:nick,''),
                      NULLIF(:notes,'')
                    FROM new_id nid
                    RETURNING id
                    """
                ),
                {
                    "bday": bday,
                    "bg": bg,
                    "stage": stage,
                    "nick": nick,
                    "notes": notes,
                },
            ).mappings().first()

            if not fish_row:
                warnings.append(f"Failed to insert fish for nickname={nick!r}")
                continue

            fish_id = fish_row["id"]
            fish_inserted += 1

            base_raw = row.get("transgene_base_code", "") or ""
            allele_nick = row.get("allele_nickname", "") or ""
            zyg = row.get("zygosity", "") or ""
            if not base_raw or not allele_nick:
                continue

            base_norm = normalize_base_code(base_raw)
            if not base_norm:
                warnings.append(
                    f"Skipping allele link for fish nickname={nick!r}: empty base_code after normalization."
                )
                continue

            allele_row = cx.execute(
                text(
                    """
                    SELECT allele_number
                    FROM public.transgene_alleles
                    WHERE transgene_base_code = :b
                      AND allele_nickname = :n
                    LIMIT 1;
                    """
                ),
                {"b": base_norm, "n": allele_nick},
            ).mappings().first()

            if not allele_row:
                warnings.append(
                    f"Skipping allele link for fish nickname={nick!r}: no transgene_alleles match for base={base_norm!r}, allele_nickname={allele_nick!r}."
                )
                continue

            allele_number = allele_row["allele_number"]

            cx.execute(
                text(
                    """
                    INSERT INTO public.join_fish_transgene_alleles
                      (fish_id, transgene_base_code, allele_number, zygosity)
                    VALUES
                      (:fid, :b, :n, NULLIF(:zyg,''))
                    """
                ),
                {"fid": fish_id, "b": base_norm, "n": allele_number, "zyg": zyg},
            )
            allele_links += 1

    return {
        "rows": len(df),
        "fish_inserted": fish_inserted,
        "allele_links": allele_links,
        "warnings": warnings,
    }
