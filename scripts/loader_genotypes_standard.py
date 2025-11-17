#!/usr/bin/env python
from __future__ import annotations

import sys
import pathlib
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.loaders import get_engine_from_env
from carp_app.etl.loader_genotypes import (
    load_genotypes_from_csv,
    load_genotype_alleles_from_csv,
)


def main(argv: list[str] | None = None) -> int:
    base = Path("carp_app/seed_kits/2025-11-15-121231-autoload")

    genotypes_csv = base / "genotypes_from_standard_fish.csv"
    genotype_alleles_csv = base / "genotype_alleles_from_standard_fish.csv"

    engine = get_engine_from_env()
    print(f"DB_URL={engine.url}")

    if genotypes_csv.exists():
        summary = load_genotypes_from_csv(genotypes_csv, engine=engine)
        print(f"Loaded genotypes from {genotypes_csv}")
        print(f"  rows:     {summary['rows']}")
        print(f"  inserted: {summary['inserted']}")
        print(f"  updated:  {summary['updated']}")
        if summary.get("warnings"):
            print("  Warnings:")
            for w in summary["warnings"]:
                print(f"    - {w}")
    else:
        print(f"Genotypes CSV not found at {genotypes_csv}")

    if genotype_alleles_csv.exists():
        summary = load_genotype_alleles_from_csv(genotype_alleles_csv, engine=engine)
        print(f"Loaded genotype alleles from {genotype_alleles_csv}")
        print(f"  rows:          {summary['rows']}")
        print(f"  links_created: {summary['links_created']}")
        if summary.get("warnings"):
            print("  Warnings:")
            for w in summary["warnings"]:
                print(f"    - {w}")
    else:
        print(f"Genotype-alleles CSV not found at {genotype_alleles_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
