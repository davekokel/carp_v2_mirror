from __future__ import annotations

import sys
import pathlib
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.util import get_engine_from_env


def load_tanks_for_standard_fish(engine: Optional[Engine] = None) -> dict:
    if engine is None:
        engine = get_engine_from_env()

    with engine.begin() as cx:
        fish_rows = cx.execute(
            text(
                """
                SELECT
                  id,
                  fish_code,
                  birthday,
                  genetic_background,
                  line_building_stage,
                  nickname,
                  notes
                FROM public.fish_instance
                ORDER BY birthday, fish_code
                """
            )
        ).mappings().all()

    tanks_inserted = 0
    memberships_inserted = 0

    with engine.begin() as cx:
        for f in fish_rows:
            fish_id = f["id"]
            fish_code = f["fish_code"]
            birthday = f["birthday"]
            nickname = (f["nickname"] or "").strip()
            bg = (f["genetic_background"] or "").strip()
            stage = (f["line_building_stage"] or "").strip()

            tank_code = f"TNK-{fish_code}"

            tank_id = cx.execute(
                text("SELECT id FROM public.tanks WHERE tank_code = :code LIMIT 1"),
                {"code": tank_code},
            ).scalar()

            if not tank_id:
                parts = []
                if nickname:
                    parts.append(nickname)
                if bg:
                    parts.append(f"bg={bg}")
                if stage:
                    parts.append(f"stage={stage}")
                tank_notes = " | ".join(parts) or None

                tank_id = cx.execute(
                    text(
                        """
                        INSERT INTO public.tanks (tank_code, location, status, volume_l, notes)
                        VALUES (:code, NULL, 'active', NULL, :notes)
                        RETURNING id
                        """
                    ),
                    {"code": tank_code, "notes": tank_notes},
                ).scalar()
                tanks_inserted += 1

            existing_mem = cx.execute(
                text(
                    """
                    SELECT id
                    FROM public.tank_memberships
                    WHERE tank_id = :tid
                      AND fish_id = :fid
                      AND role = 'resident'
                      AND ended_at IS NULL
                    LIMIT 1
                    """
                ),
                {"tid": tank_id, "fid": fish_id},
            ).scalar()

            if not existing_mem:
                cx.execute(
                    text(
                        """
                        INSERT INTO public.tank_memberships
                          (tank_id, fish_id, role, started_at, notes)
                        VALUES
                          (:tid, :fid, 'resident', COALESCE(:start_at, now()), NULL)
                        """
                    ),
                    {"tid": tank_id, "fid": fish_id, "start_at": birthday},
                )
                memberships_inserted += 1

    return {
        "fish_seen": len(fish_rows),
        "tanks_inserted": tanks_inserted,
        "memberships_inserted": memberships_inserted,
    }


def main() -> None:
    engine = get_engine_from_env()
    summary = load_tanks_for_standard_fish(engine)
    print("Summary:", summary)


if __name__ == "__main__":
    main()
