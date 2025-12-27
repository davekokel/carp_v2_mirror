#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def run_env(cmd: list[str], extra_env: dict[str, str]) -> None:
    env = os.environ.copy()
    env.update(extra_env)
    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def run_psql(sql: str) -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL must be set")
    print("\n[RUN] psql (cleanup legacy clutches)")
    subprocess.run(
        ["psql", db_url, "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True,
    )


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL must be set")
    print("[DB]", db_url)

    repo = Path(__file__).resolve().parents[1]
    v4 = repo / "seed_kits" / "legacy_wrangling_v4"
    work = v4 / "working"

    # Canonical ROI feed outputs
    roi_csv_loader = work / "legacy_imaging_annotations_for_loader_v9_compat.csv"
    roi_csv_loader_all = work / "legacy_imaging_annotations_for_loader_v9_compat.csv"
    roi_csv_for_db = work / "legacy_imaging_annotations_for_db_v9.csv"
    roi_csv_db_compat = work / "legacy_imaging_annotations_for_db_v9_compat.csv"

    # Derived from the SAME canonical ROI loader feed (writes into v4/working)
    clutches_v9_out = work / "legacy_clutches_v9.csv"
    memberships_v9_out = work / "legacy_clutch_memberships_v9.csv"
    clutches_v9_for_loader = work / "legacy_clutches_v9_for_loader.csv"

    imaging_sheet_xlsx = v4 / "raw" / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"

    # Ideal sheet outputs (v4)
    ideal_tsv = work / "ideal_imaging_import_sheet_v4.tsv"
    ideal_fixed_tsv = work / "ideal_imaging_import_sheet_v4.fixed.tsv"

    # Patch CSVs for loader_legacy_clutches (derived from ideal sheet)
    patch_geno_mem_histone = work / "legacy_clutches_patch_genotypes__ideal_mem_histone.csv"
    patch_geno_mem_mito = work / "legacy_clutches_patch_genotypes__ideal_mem_mito.csv"

    # Clutch→treatment mapping from v4 ROI sheet
    clutch_treat_map_csv = work / "clutch_treatment_mapping_from_v4__ideal.csv"
    clutch_treat_map_db_csv = work / "clutch_treatment_mapping_from_v4__ideal.dbclutchcode.csv"

    # 0) Normalize imaging sheet (so downstream steps have a stable, greppable TSV)
    run(["python", "seed_kits/legacy_wrangling_v4/scripts/01_read_imaging_sheet_v4.py"])

    # 1) Canonical ROI extraction + deterministic linking to imaging sheet
    run(["python", "seed_kits/legacy_wrangling_v4/scripts/01_link_v4.py"])

    # 2) Build ROI loader-compatible CSV FROM THE CANONICAL ROI FEED
    run(["python", "seed_kits/legacy_wrangling_v4/scripts/05_make_v9_loader_compat_from_link_v4.py"])

    # 3) Enrich ROI rows (genotype/treatment rollups etc.) FROM THE SAME CANONICAL ROI FEED
    run(["python", "-u", "seed_kits/legacy_wrangling_v4/scripts/02_enrich_v4.py"])
    run(["python", "seed_kits/legacy_wrangling_v4/scripts/03_qc_v4.py"])

    # 4) Build DB-compat ROI CSV aligned to the enriched ROI set (same roi_dir universe)
    run(["python", "seed_kits/legacy_wrangling_v4/scripts/05_make_v9_compat_from_v4.py"])

    # 5) Apply slot orientation (uses the imaging sheet + db_compat plate/slot IDs)
    run([
        "python", "scripts/v9_backfill_legacy_slot_orientation.py",
        "--sheet-xlsx", str(imaging_sheet_xlsx),
        "--roi-csv", str(roi_csv_db_compat),
    ])

    # 6) Build clutches + memberships from the SAME ROI FEED as the ROI loader (prevents drift)
    run([
        "python", "scripts/v9_build_legacy_clutches_from_v9.py",
        "--csv", str(roi_csv_loader_all),
        "--out-dir", str(work),
    ])

    # 7) Prepare clutch loader CSV (joins to roi_for_db for genotype basecodes)
    run([
        "python", "scripts/v9_prepare_legacy_clutches_for_loader.py",
        "--in-csv", str(clutches_v9_out),
        "--out-csv", str(clutches_v9_for_loader),
        "--roi-compat-csv", str(roi_csv_db_compat),
        "--roi-for-db-csv", str(roi_csv_for_db),
    ])

    # 8) CLEANUP legacy clutches before reloading (prevents LCL-#### collisions)
    run_psql(
        """
        BEGIN;

        CREATE TEMP TABLE _legacy_clutches AS
        SELECT id
        FROM public.clutches
        WHERE source_system = 'legacy_imaging';

        DELETE FROM public.imaging_clutch_memberships m
        USING _legacy_clutches lc
        WHERE m.clutch_id = lc.id;

        DELETE FROM public.join_clutch_treatments j
        USING _legacy_clutches lc
        WHERE j.clutch_id = lc.id;

        DELETE FROM public.clutches c
        USING _legacy_clutches lc
        WHERE c.id = lc.id;

        COMMIT;
        """
    )

    # 9) Load clutches (and set genotype_v11_id via loader)
    run([
        "python", "scripts/loader_legacy_clutches.py",
        "--csv", str(clutches_v9_for_loader),
        "--batch", "legacy_clutch_inference_v4",
    ])

    # 10) Load plates/slots/ROIs from the loader compat feed
    run([
        "python", "scripts/v9_load_imaging_legacy_rois.py",
        "--csv", str(roi_csv_loader_all),
    ])

    # 11) Load memberships derived from the same clutch build step (same feed)
    run([
        "python", "scripts/v9_load_imaging_clutch_memberships_from_v9.py",
        "--csv", str(memberships_v9_out),
    ])

    # 11b) Ensure every ROI slot has a clutch (even if genotype evidence is missing)
    run([
        "python", "scripts/v9_attach_missing_clutches_for_all_slots.py",
        "--batch", "legacy_attach_missing_slots_v4",
    ])

    # 12) Build + load treatments (v10) from enriched ROI feed (kept as-is)
    run([
        "python", "scripts/v10_build_legacy_treatments_from_v9.py",
        "--roi-csv", str(roi_csv_for_db),
        "--out-csv", str(repo / "seed_kits" / "2025-11-15-121231-autoload" / "treatments_v10.csv"),
    ])
    run([
        "python", "scripts/v10_load_treatments_from_csv.py",
        "--csv", str(repo / "seed_kits" / "2025-11-15-121231-autoload" / "treatments_v10.csv"),
    ])

    # 13) Build IDEAL TSV (pre-DB) with legacy_clutch_key + canonical genotype/treatment
    run(["python", "seed_kits/legacy_wrangling_v4/scripts/07c_enrich_treatments_from_sheet_v4.py"])
    run([
        "python", "seed_kits/legacy_wrangling_v4/scripts/07e_patch_ideal_treatments_v4.py",
        "--in-tsv", str(work / "ideal_with_treatments_v4.tsv"),
        "--out-tsv", str(work / "ideal_with_treatments_v4.patched.tsv"),
    ])
    run(["python", "seed_kits/legacy_wrangling_v4/scripts/07b_enrich_genotypes_from_sheet_v4.py"])
    run([
        "python", "seed_kits/legacy_wrangling_v4/scripts/07f_patch_ideal_genotypes_v4.py",
        "--in-tsv", str(work / "ideal_with_genotypes_v4.tsv"),
        "--out-tsv", str(work / "ideal_with_genotypes_v4.patched.tsv"),
    ])
    run([
        "python", "seed_kits/legacy_wrangling_v4/scripts/07d_merge_ideal_parts_v4.py",
        "--geno-tsv", str(work / "ideal_with_genotypes_v4.patched.tsv"),
        "--treat-tsv", str(work / "ideal_with_treatments_v4.patched.tsv"),
    ])

    # 14) Patch genotypes from the fixed ideal sheet back into clutches (repeatable)
    run([
        "python", "scripts/v11_patch_genotypes_from_ideal_sheet_v4.py",
        "--only-slug", "mem-histone",
        "--out-csv", str(patch_geno_mem_histone),
    ])
    run([
        "python", "scripts/loader_legacy_clutches.py",
        "--csv", str(patch_geno_mem_histone),
        "--batch", "legacy_clutch_inference_v4",
    ])

    run([
        "python", "scripts/v11_patch_genotypes_from_ideal_sheet_v4.py",
        "--only-slug", "mem-mito",
        "--out-csv", str(patch_geno_mem_mito),
    ])
    run([
        "python", "scripts/loader_legacy_clutches.py",
        "--csv", str(patch_geno_mem_mito),
        "--batch", "legacy_clutch_inference_v4",
    ])

    # 15) Build + apply clutch→treatment mapping from IDEAL fixed TSV (DB clutch_code)
    run([
        "python", "scripts/v11_build_clutch_treatment_mapping_from_v4_dbclutchcode.py",
        "--ideal-tsv", str(work / "ideal_imaging_import_sheet_v4.fixed.tsv"),
        "--out-csv", str(clutch_treat_map_db_csv),
    ])
    run_env(
        ["python", "scripts/v11_apply_clutch_treatment_mapping_from_v4.py"],
        {"CLUTCH_TREAT_MAP_CSV": str(clutch_treat_map_db_csv)},
    )

print("\n[OK] legacy imaging pipeline (v4) completed cleanly")


if __name__ == "__main__":
    main()