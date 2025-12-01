#!/usr/bin/env python3
from __future__ import annotations
import os

from sqlalchemy import create_engine, text


def norm_stage(seg: str) -> str:
    seg = (seg or "").strip().lower()
    if seg in ("injection", "injections"):
        return "injections"
    if seg in ("p0", "p-0"):
        return "p0"
    if seg in ("f1", "f-1"):
        return "f1"
    if seg in ("f2", "f-2"):
        return "f2"
    if seg in ("stable",):
        return "stable"
    if seg in ("founder",):
        return "founder"
    return seg or None


def main() -> None:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    engine = create_engine(url)

    updated = 0
    with engine.begin() as cx:
        # Pull fish_code and current instance_stage
        res = cx.execute(
            text(
                """
                SELECT id::text AS fish_id,
                       fish_code,
                       instance_stage
                FROM public.fish_instances_v10
                """
            )
        )
        rows = res.fetchall()

        for row in rows:
            fish_id = row[0]
            fish_code = (row[1] or "").strip()
            current_stage = (row[2] or None)

            # Skip if already set
            if current_stage:
                continue

            # Expect code fragments separated by '-'
            parts = fish_code.split("-")
            # Minimal pattern: ["LINE", "<uuid>", "<stage>", "<serial>"]
            if len(parts) < 4:
                continue

            stage_raw = parts[2]
            stage = norm_stage(stage_raw)
            if not stage:
                continue

            cx.execute(
                text(
                    """
                    UPDATE public.fish_instances_v10
                    SET instance_stage = :stage
                    WHERE id::text = :fid
                    """
                ),
                {"stage": stage, "fid": fish_id},
            )
            updated += 1

    print(f"[v11_backfill_fish_instance_stage_from_code] updated instance_stage for {updated} fish instances.")


if __name__ == "__main__":
    main()
