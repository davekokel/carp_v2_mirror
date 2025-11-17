#!/usr/bin/env python
from __future__ import annotations

import sys
import pathlib
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.loaders import get_engine_from_env
from carp_app.etl.loader_fish_legacy_from_rois import load_legacy_fish_from_rois


def main(argv: list[str] | None = None) -> int:
    base = Path("carp_app/seed_kits/standard_from_legacy")
    csv_path = base / "fish_instances_standard_from_legacy.csv"

    engine = get_engine_from_env()
    print(f"DB_URL={engine.url}")

    summary = load_legacy_fish_from_rois(csv_path, engine=engine)
    print(f"Loaded legacy fish from {csv_path}")
    print(f"  rows:             {summary['rows']}")
    print(f"  fish_inserted:    {summary['fish_inserted']}")
    print(f"  skipped_existing: {summary['skipped_existing']}")
    if summary["warnings"]:
        print("  Warnings:")
        for w in summary["warnings"]:
            print(f"    - {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
