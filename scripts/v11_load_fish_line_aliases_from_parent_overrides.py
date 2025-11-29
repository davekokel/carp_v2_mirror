from __future__ import annotations

import os
from typing import Dict

import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DB_URL")
OVERRIDES_CSV = "seed_kits/legacy_wrangling_v2/working/legacy_parent_line_overrides_v11.csv"


def main() -> None:
    if not DB_URL:
        raise RuntimeError("DB_URL is not set")
    eng = create_engine(DB_URL)

    if not os.path.exists(OVERRIDES_CSV):
        raise FileNotFoundError(f"Overrides CSV not found: {OVERRIDES_CSV}")

    df = pd.read_csv(OVERRIDES_CSV)
    if not {"parent_label", "line_nickname"}.issubset(df.columns):
        raise ValueError(f"{OVERRIDES_CSV} must have parent_label,line_nickname columns")

    with eng.begin() as cx:
        lines = pd.read_sql(
            text("SELECT id::text AS line_id, nickname::text AS nickname FROM public.fish_lines"),
            cx,
        )
    nick_to_id: Dict[str, str] = {
        str(row["nickname"]).strip(): str(row["line_id"])
        for _, row in lines.iterrows()
        if str(row["nickname"]).strip()
    }

    to_insert = []

    for _, row in df.iterrows():
        alias = str(row["parent_label"] or "").strip()
        ln   = str(row["line_nickname"] or "").strip()
        if not alias or not ln:
            continue
        line_id = nick_to_id.get(ln)
        if not line_id:
            continue
        to_insert.append((line_id, alias))

    if not to_insert:
        print("[INFO] No aliases to insert.")
        return

    with eng.begin() as cx:
        inserted = 0
        for line_id, alias in to_insert:
            cx.execute(
                text(
                    """
                    INSERT INTO public.fish_line_aliases (line_id, alias, alias_kind)
                    VALUES (CAST(:lid AS uuid), :alias, 'legacy_parent')
                    ON CONFLICT (line_id, alias) DO NOTHING
                    """
                ),
                {"lid": line_id, "alias": alias},
            )
            inserted += 1

    print(f"[OK] Inserted up to {inserted} fish_line_aliases row(s).")


if __name__ == "__main__":
    main()
