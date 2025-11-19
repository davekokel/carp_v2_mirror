from __future__ import annotations
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

BASE = Path(__file__).resolve().parents[1]
IMPORT_BATCH_ID = "seedkit_2025-11-15"


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL is not set")

    engine = create_engine(db_url)

    with engine.begin() as cx:
        df_fish = pd.read_sql(
            text(
                """
                SELECT
                  id          AS fish_id,
                  fish_code
                FROM public.fish_instance
                ORDER BY fish_code
                """
            ),
            cx,
        )

    if df_fish.empty:
        raise SystemExit("[ERROR] fish_instance is empty; cannot seed tanks from fish.")

    def tank_suffix(code: str) -> str:
        if isinstance(code, str) and code.startswith("FSH-"):
            return code[4:]
        return code

    suffixes = df_fish["fish_code"].apply(tank_suffix)

    df_tanks = pd.DataFrame(
        {
            "tank_code": "TANK-" + suffixes + "-01",
            "fish_id": df_fish["fish_id"],
            "status": "active",
            "location": "",
            "volume_l": 3.0,
            "notes": "",
            "import_batch_id": IMPORT_BATCH_ID,
        }
    )

    engine = create_engine(db_url)
    with engine.begin() as cx:
        cx.execute(
            text(
                """
                ALTER TABLE public.tanks
                ADD COLUMN IF NOT EXISTS import_batch_id text
                """
            )
        )

        cx.execute(
            text(
                """
                DELETE FROM public.tanks
                WHERE import_batch_id = :batch
                """
            ),
            {"batch": IMPORT_BATCH_ID},
        )
        print(f"[INFO] Deleted existing tanks for import_batch_id={IMPORT_BATCH_ID!r}.")

        inserted = 0
        for _, row in df_tanks.iterrows():
            cx.execute(
                text(
                    """
                    INSERT INTO public.tanks (
                        tank_code,
                        fish_id,
                        status,
                        location,
                        volume_l,
                        notes,
                        import_batch_id
                    )
                    VALUES (
                        :tank_code,
                        :fish_id,
                        :status,
                        :location,
                        :volume_l,
                        :notes,
                        :import_batch_id
                    )
                    """
                ),
                row.to_dict(),
            )
            inserted += 1

        print(f"[OK] Inserted {inserted} tank(s) for batch={IMPORT_BATCH_ID!r}.")


if __name__ == "__main__":
    main()
