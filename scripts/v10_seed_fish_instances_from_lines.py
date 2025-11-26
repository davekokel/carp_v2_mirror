from __future__ import annotations

import os
import uuid
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    """
    v10: seed fish_instances_v10 from fish_lines.

    - One primary fish instance per line (for now).
    - fish_code = 'FSH-' + first 8 chars of the fish UUID (independent of line_code).
    - Idempotent: if a fish_instance_v10 already exists for a line_id, skip it.
    """
    db_url = os.environ.get("DB_URL")
    engine = get_engine(db_url)

    # Load all lines
    sql_lines = text(
        """
        SELECT
          id::text       AS line_id,
          line_code,
          nickname,
          genetic_background,
          line_building_stage
        FROM public.fish_lines
        ORDER BY line_code
        """
    )
    with engine.begin() as cx:
        df_lines = pd.read_sql(sql_lines, cx)

    if df_lines.empty:
        print("[v10_seed_fish_instances] no fish_lines rows; nothing to do.")
        return

    # Find which lines already have fish_instances_v10
    sql_existing = text(
        """
        SELECT DISTINCT line_id::text AS line_id
        FROM public.fish_instances_v10
        """
    )
    with engine.begin() as cx:
        df_existing = pd.read_sql(sql_existing, cx)

    existing_line_ids = set(df_existing["line_id"].astype(str)) if not df_existing.empty else set()
    print(f"[v10_seed_fish_instances] existing fish_instances_v10 for {len(existing_line_ids)} line(s)")

    # Prepare insert statement
    sql_insert = text(
        """
        INSERT INTO public.fish_instances_v10 (
          id,
          fish_code,
          line_id,
          birthday,
          notes,
          created_at
        )
        VALUES (
          :id,
          :fish_code,
          :line_id,
          NULL,
          :notes,
          now()
        )
        """
    )

    inserted = 0
    skipped = 0

    with engine.begin() as cx:
        for _, row in df_lines.iterrows():
            line_id = str(row["line_id"])
            if line_id in existing_line_ids:
                skipped += 1
                continue

            # Generate a new fish UUID and code independent of line_code
            fish_id = str(uuid.uuid4())
            fish_code = f"FSH-{fish_id.replace('-', '')[:8]}"

            notes_parts = []
            nickname = str(row["nickname"] or "").strip()
            bg = str(row["genetic_background"] or "").strip()
            stage = str(row["line_building_stage"] or "").strip()
            if nickname:
                notes_parts.append(f"line nickname={nickname}")
            if bg:
                notes_parts.append(f"bg={bg}")
            if stage:
                notes_parts.append(f"stage={stage}")
            notes = "; ".join(notes_parts) if notes_parts else None

            cx.execute(
                sql_insert,
                {
                    "id": fish_id,
                    "fish_code": fish_code,
                    "line_id": line_id,
                    "notes": notes,
                },
            )
            inserted += 1

    print(f"[v10_seed_fish_instances] inserted {inserted} fish_instances_v10")
    print(f"[v10_seed_fish_instances] skipped  {skipped} line(s) that already had fish_instances_v10")


if __name__ == "__main__":
    main()
