#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
import pathlib
from pathlib import Path

# ---- path bootstrap --------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.loaders import (
    get_engine_from_env,
    load_plasmids_from_csv,
    load_rnas_from_csv,
    load_dyes_from_csv,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load v7 constructs (plasmids, RNAs, dyes) from standard CSVs into the DB pointed at by DB_URL."
    )
    parser.add_argument(
        "--plasmids",
        type=str,
        help="Path to standard plasmids CSV (plasmid_base_code, name, nickname, notes).",
    )
    parser.add_argument(
        "--rnas",
        type=str,
        help="Path to standard RNAs CSV (rna_base_code, name, notes).",
    )
    parser.add_argument(
        "--dyes",
        type=str,
        help="Path to standard dyes CSV (dye_base_code, name, notes).",
    )
    args = parser.parse_args(argv)

    if not (args.plasmids or args.rnas or args.dyes):
        parser.error("At least one of --plasmids, --rnas, or --dyes is required")

    engine = get_engine_from_env()

    if args.plasmids:
        csv_path = Path(args.plasmids)
        if not csv_path.exists():
            parser.error(f"Plasmid CSV not found: {csv_path}")
        summary = load_plasmids_from_csv(csv_path, engine=engine)
        print(f"Loaded plasmids from {csv_path}")
        print(f"  rows:     {summary['rows']}")
        print(f"  inserted: {summary['inserted']}")
        print(f"  updated:  {summary['updated']}")
        if summary["warnings"]:
            print("  Warnings:")
            for w in summary["warnings"]:
                print(f"    - {w}")

    if args.rnas:
        csv_path = Path(args.rnas)
        if not csv_path.exists():
            parser.error(f"RNA CSV not found: {csv_path}")
        summary = load_rnas_from_csv(csv_path, engine=engine)
        print(f"Loaded RNAs from {csv_path}")
        print(f"  rows:     {summary['rows']}")
        print(f"  inserted: {summary['inserted']}")
        print(f"  updated:  {summary['updated']}")
        if summary["warnings"]:
            print("  Warnings:")
            for w in summary["warnings"]:
                print(f"    - {w}")

    if args.dyes:
        csv_path = Path(args.dyes)
        if not csv_path.exists():
            parser.error(f"Dye CSV not found: {csv_path}")
        summary = load_dyes_from_csv(csv_path, engine=engine)
        print(f"Loaded dyes from {csv_path}")
        print(f"  rows:     {summary['rows']}")
        print(f"  inserted: {summary['inserted']}")
        print(f"  updated:  {summary['updated']}")
        if summary["warnings"]:
            print("  Warnings:")
            for w in summary["warnings"]:
                print(f"    - {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
