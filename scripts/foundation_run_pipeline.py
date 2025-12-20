#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess


def run(cmd: list[str]) -> None:
    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL must be set")
    print("[DB]", db_url)

    run([
        "python", "scripts/v8_load_fluors_tags_fusions.py",
        "--fluors-csv", "seed_kits/2025-11-15-121231-autoload/fluors.csv",
        "--tags-file",  "seed_kits/2025-11-15-121231-autoload/tags.xlsx",
    ])

    run([
        "python", "scripts/v8_load_fluor_aliases_from_csv.py",
        "--alias-csv", "seed_kits/2025-11-15-121231-autoload/alias.csv",
    ])

    run([
        "python", "-m", "carp_app.etl.loader_dyes",
        "--csv", "seed_kits/2025-11-15-121231-autoload/dyes.csv",
    ])

    run([
        "python", "scripts/v10_load_constructs_from_csv.py",
        "--constructs-csv", "seed_kits/2025-11-15-121231-autoload/constructs_plasmid.csv",
    ])

    run([
        "python", "scripts/v10_load_construct_fusions_from_csv.py",
        "--constructs-csv", "seed_kits/2025-11-15-121231-autoload/constructs_plasmid.csv",
    ])

    run(["python", "scripts/v9_build_genetic_backgrounds_seed.py"])
    run(["python", "scripts/v9_load_genetic_backgrounds_seed.py"])

    run([
        "python", "scripts/v11_seed_fish_transgenics_from_csv.py",
        "--csv", "seed_kits/2025-11-15-121231-autoload/fish_transgenics.csv",
    ])

    run([
        "python", "scripts/v11_seed_fish_treated_from_csv.py",
        "--csv", "seed_kits/2025-11-15-121231-autoload/fish_treated.csv",
    ])

    run(["python", "scripts/v11_seed_fish_transgene_alleles_from_lines.py"])

    print("\n[OK] foundation pipeline completed cleanly")


if __name__ == "__main__":
    main()
