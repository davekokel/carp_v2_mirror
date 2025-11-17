#!/usr/bin/env python
from __future__ import annotations

import sys
import pathlib
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.loaders import get_engine_from_env
from carp_app.etl.loader_transgenes import seed_transgenes_from_genotype_alleles


def main(argv: list[str] | None = None) -> int:
    base = Path("carp_app/seed_kits/2025-11-15-121231-autoload")
    geno_alleles_csv = base / "genotype_alleles_from_standard_fish.csv"

    engine = get_engine_from_env()
    print(f"DB_URL={engine.url}")

    if not geno_alleles_csv.exists():
        print(f"Genotype-alleles CSV not found at {geno_alleles_csv}", file=sys.stderr)
        return 1

    summary = seed_transgenes_from_genotype_alleles(geno_alleles_csv, engine=engine)

    print(f"Seeded transgenes from {geno_alleles_csv}")
    print(f"  rows:                {summary['rows']}")
    print(f"  transgenes_inserted: {summary['transgenes_inserted']}")
    print(f"  alleles_inserted:    {summary['alleles_inserted']}")
    if summary["warnings"]:
        print("  Warnings:")
        for w in summary["warnings"]:
            print(f"    - {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
