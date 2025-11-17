#!/usr/bin/env python
from __future__ import annotations

import sys
import pathlib
from pathlib import Path
import argparse

# ---- path bootstrap --------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.loaders import get_engine_from_env, load_fish_standard_from_excel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load standard fish instances from fish.xlsx into public.fish_instance."
    )
    parser.add_argument(
        "--fish-xlsx",
        type=str,
        required=True,
        help="Path to standard fish Excel file (e.g. carp_app/seed_kits/.../fish.xlsx)",
    )
    args = parser.parse_args(argv)

    xlsx_path = Path(args.fish_xlsx)
    if not xlsx_path.exists():
        parser.error(f"Fish Excel file not found: {xlsx_path}")

    engine = get_engine_from_env()
    summary = load_fish_standard_from_excel(xlsx_path, engine=engine)

    print(f"Loaded fish from {xlsx_path}")
    print(f"  rows:     {summary['rows']}")
    print(f"  inserted: {summary['inserted']}")
    if summary["warnings"]:
        print("  Warnings:")
        for w in summary["warnings"]:
            print(f"    - {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
