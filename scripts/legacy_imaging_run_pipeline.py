#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

import tomllib


def run(cmd: list[str]) -> None:
    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="carp_app/pipelines/legacy_imaging_config.toml",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL must be set")
    print("[DB]", db_url)

    cfg_path = Path(args.config).resolve()
    cfg = tomllib.loads(cfg_path.read_text())

    repo = Path(__file__).resolve().parents[1]
    working = (repo / cfg["paths"]["working_dir"]).resolve()
    raw_dir = (repo / cfg["paths"]["raw_dir"]).resolve()

    roi_csv_v9 = (working / "legacy_imaging_annotations_for_db_v9_compat.csv").resolve()
    clutch_csv_v9 = (repo / "seed_kits" / "legacy_wrangling_v2" / "working" / "legacy_clutches_v9.csv").resolve()
    memberships_csv_v9 = (repo / "seed_kits" / "legacy_wrangling_v2" / "working" / "legacy_clutch_memberships_v9.csv").resolve()
    clutch_for_loader_csv = (working / "legacy_clutches_v9_for_loader.csv").resolve()

    imaging_sheet_xlsx = (repo / cfg["imaging_sheet"]["xlsx"]).resolve()

    run(["python", "seed_kits/legacy_wrangling_v3/scripts/02_infer_missing_imaging_rows.py"])
    run(["python", "seed_kits/legacy_wrangling_v3/scripts/01_link.py"])
    run(["python", "-u", "seed_kits/legacy_wrangling_v3/scripts/02_enrich.py"])

    run([
        "python", "seed_kits/legacy_wrangling_v3/scripts/05_make_v9_compat_from_v3.py",
    ])

    run([
        "python", "scripts/v9_backfill_legacy_slot_orientation.py",
        "--sheet-xlsx", str(imaging_sheet_xlsx),
        "--roi-csv", str(roi_csv_v9),
    ])

    run([
        "python", "scripts/v9_build_legacy_clutches_from_v9.py",
        "--csv", str(roi_csv_v9),
    ])

    run([
        "python", "scripts/v9_prepare_legacy_clutches_for_loader.py",
        "--in-csv", str(clutch_csv_v9),
        "--out-csv", str(clutch_for_loader_csv),
    ])

    run([
        "python", "scripts/loader_legacy_clutches.py",
        "--csv", str(clutch_for_loader_csv),
        "--batch", cfg["batch_ids"]["genotypes"],
    ])

    run([
        "python", "scripts/v9_load_imaging_clutch_memberships_from_v9.py",
        "--csv", str(memberships_csv_v9),
    ])

    run([
        "python", "scripts/v10_build_legacy_treatments_from_v9.py",
        "--roi-csv", str(roi_csv_v9),
        "--out-csv", "seed_kits/2025-11-15-121231-autoload/treatments_v10.csv",
    ])

    run([
        "python", "scripts/v10_load_treatments_from_csv.py",
        "--csv", "seed_kits/2025-11-15-121231-autoload/treatments_v10.csv",
    ])

    run([
        "python", "scripts/v11_build_clutch_treatment_mapping_from_v9.py",
        "--roi-csv", str(roi_csv_v9),
        "--out-csv", str(working / "clutch_treatment_mapping_v11.csv"),
    ])

    run([
        "python", "scripts/v11_seed_legacy_treatments_from_mapping.py",
        "--mapping-csv", str(working / "clutch_treatment_mapping_v11.csv"),
    ])

    run(["python", "scripts/v11_apply_clutch_treatment_mapping.py"])
    run(["python", "scripts/v11_frontfill_imaging_clutch_memberships_treated.py"])

    run([
        "python", "scripts/v11_load_legacy_roi_enriched_v9.py",
        "--config", str(cfg_path),
    ])

    run([
        "python", "scripts/v11_load_legacy_clutch_parents_v9.py",
        "--csv", str(clutch_for_loader_csv),
    ])

    run([
        "python", "scripts/v11_load_legacy_parent_definitions_v9.py",
        "--config", str(cfg_path),
    ])

    run(["python", "scripts/v11_seed_legacy_genotypes_from_enriched_roi.py"])
    run(["python", "scripts/v11_seed_legacy_genotypes_from_parents.py"])
    run(["python", "scripts/v11_seed_genotype_constructs_from_genotypes.py"])
    run(["python", "scripts/v11_seed_clutch_expected_genotypes_from_parents.py"])
    run(["python", "scripts/v11_seed_transgenes_from_legacy_parents.py"])
    run(["python", "scripts/v11_normalize_genotype_basecodes_from_constructs.py"])

    print("\n[OK] legacy imaging pipeline completed cleanly")


if __name__ == "__main__":
    main()
