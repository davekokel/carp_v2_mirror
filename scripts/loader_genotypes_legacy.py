from __future__ import annotations

import sys
from pathlib import Path

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.util import get_engine_from_env  # noqa: E402
from carp_app.etl.loader_genotypes import (        # noqa: E402
    load_genotypes_from_csv,
    load_genotype_alleles_from_csv,
)
from carp_app.config.seed_kits import LEGACY_FINAL  # noqa: E402


def main() -> None:
    base = LEGACY_FINAL

    genotypes_csv = base / "legacy_genotypes.csv"
    geno_alleles_csv = base / "legacy_genotype_alleles.csv"

    engine = get_engine_from_env()
    print(f"DB_URL={engine.url}")

    print(f"[INFO] Loading LEGACY genotypes from {genotypes_csv}")
    g_summary = load_genotypes_from_csv(genotypes_csv, engine=engine)
    print(f"[RESULT] genotypes: {g_summary}")

    print(f"[INFO] Loading LEGACY genotype_alleles from {geno_alleles_csv}")
    ga_summary = load_genotype_alleles_from_csv(geno_alleles_csv, engine=engine)
    print(f"[RESULT] genotype_alleles: {ga_summary}")

    print("[DONE] Legacy genotypes import complete.")


if __name__ == "__main__":
    main()
