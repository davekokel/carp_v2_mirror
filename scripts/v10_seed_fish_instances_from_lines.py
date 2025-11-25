from __future__ import annotations

import argparse
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: seed fish_instances_v10 from existing fish_lines (one instance per line)."
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    engine = get_engine(args.db_url)

    select_lines = text(
        """
        SELECT
          id::text       AS line_id,
          line_code,
          nickname,
          genetic_background
        FROM public.fish_lines
        ORDER BY created_at
        """
    )

    insert_instance = text(
        """
        INSERT INTO public.fish_instances_v10 (
          fish_code,
          line_id,
          birthday,
          notes,
          created_at
        )
        VALUES (
          :fish_code,
          :line_id,
          NULL,
          :notes,
          now()
        )
        ON CONFLICT (fish_code) DO NOTHING
        """
    )

    inserted = 0
    with engine.begin() as cx:
        rows = cx.execute(select_lines).fetchall()
        for row in rows:
            line_id = row._mapping["line_id"]
            line_code = row._mapping["line_code"]
            fish_code = f"FSH-{line_code[-8:]}"
            notes = f"Seed instance for line {line_code}"
            cx.execute(
                insert_instance,
                {
                    "fish_code": fish_code,
                    "line_id": line_id,
                    "notes": notes,
                },
            )
            inserted += 1

    print(f"[v10_seed_fish_instances] inserted {inserted} fish_instances_v10")


if __name__ == "__main__":
    main()
