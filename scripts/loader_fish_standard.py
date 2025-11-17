#!/usr/bin/env python
from __future__ import annotations

import sys
import pathlib
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.loaders import get_engine_from_env
from carp_app.etl.loader_fish_standard import load_fish_standard_from_xlsx


def main(argv: list[str] | None = None) -> int:
    base = Path("carp_app/seed_kits/2025-11-15-121231-autoload")
    fish_xlsx = base / "fish.xlsx"

    engine = get_engine_from_env()
    print(f"DB_URL={engine.url}")

    summary = load_fish_standard_from_xlsx(fish_xlsx, engine=engine)

    print(f"Loaded fish from {fish_xlsx}")
    print(f"  rows:          {summary['rows']}")
    print(f"  fish_inserted: {summary['fish_inserted']}")
    print(f"  allele_links:  {summary['allele_links']}")
    if summary["warnings"]:
        print("  Warnings:")
        for w in summary["warnings"]:
            print(f"    - {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
