#!/usr/bin/env python
from __future__ import annotations

import sys
import pathlib
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.loaders import (
    get_engine_from_env,
    load_fluors_from_csv,
    load_tags_from_excel,
)
from carp_app.etl.fusions_loaders import (
    load_plasmid_fusions_from_csv,
    load_rna_fusions_from_csv,
)


def main(argv: list[str] | None = None) -> int:
    base = Path("seed_kits/2025-11-15-121231-autoload")

    fluors_csv = base / "fluors.csv"
    tags_xlsx = base / "tags.xlsx"
    plasmid_fusions_csv = base / "plasmid_fusions.csv"
    rna_fusions_csv = base / "rna_fusions.csv"
    alias_csv = base / "alias.csv"

    engine = get_engine_from_env()

    print(f"DB_URL={engine.url}")

    if fluors_csv.exists():
        summary = load_fluors_from_csv(fluors_csv, alias_csv=alias_csv, engine=engine)
        print(f"Loaded fluors from {fluors_csv}")
        print(f"  rows:     {summary['rows']}")
        print(f"  inserted: {summary['inserted']}")
        print(f"  updated:  {summary['updated']}")
        if summary["warnings"]:
            print("  Warnings:")
            for w in summary["warnings"]:
                print(f"    - {w}")
    else:
        print(f"fluors CSV not found at {fluors_csv}")

    if tags_xlsx.exists():
        summary = load_tags_from_excel(tags_xlsx, alias_csv=alias_csv, engine=engine)
        print(f"Loaded tags from {tags_xlsx}")
        print(f"  rows:     {summary['rows']}")
        print(f"  inserted: {summary['inserted']}")
        print(f"  updated:  {summary['updated']}")
        if summary["warnings"]:
            print("  Warnings:")
            for w in summary["warnings"]:
                print(f"    - {w}")
    else:
        print(f"tags Excel not found at {tags_xlsx}")

    if plasmid_fusions_csv.exists():
        summary = load_plasmid_fusions_from_csv(plasmid_fusions_csv, engine=engine)
        print(f"Loaded plasmid fusions from {plasmid_fusions_csv}")
        print(f"  rows:           {summary['rows']}")
        print(f"  links_created:  {summary['links_created']}")
        if summary["warnings"]:
            print("  Warnings:")
            for w in summary["warnings"]:
                print(f"    - {w}")
    else:
        print(f"plasmid_fusions CSV not found at {plasmid_fusions_csv}")

    if rna_fusions_csv.exists():
        summary = load_rna_fusions_from_csv(rna_fusions_csv, engine=engine)
        print(f"Loaded RNA fusions from {rna_fusions_csv}")
        print(f"  rows:           {summary['rows']}")
        print(f"  links_created:  {summary['links_created']}")
        if summary["warnings"]:
            print("  Warnings:")
            for w in summary["warnings"]:
                print(f"    - {w}")
    else:
        print(f"rna_fusions CSV not found at {rna_fusions_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
