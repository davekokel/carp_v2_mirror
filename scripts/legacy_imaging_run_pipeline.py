#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL must be set")
    print("[DB]", db_url)

    repo = Path(__file__).resolve().parents[1]
    v2 = repo / "seed_kits" / "legacy_wrangling_v2"
    v3 = repo / "seed_kits" / "legacy_wrangling_v3"
    work = v3 / "working"

    roi_csv_for_db = work / "legacy_imaging_annotations_for_db_v9.csv"
    roi_csv_compat = work / "legacy_imaging_annotations_for_db_v9_compat.csv"
    memberships_v9 = v2 / "working" / "legacy_clutch_memberships_v9.csv"
    clutches_v9_in = v2 / "working" / "legacy_clutches_v9.csv"
    clutches_v9_for_loader = work / "legacy_clutches_v9_for_loader.csv"
    imaging_sheet_xlsx = v2 / "raw" / "2025-11-21-220012-imaging_sheet.xlsx"

    run(["python", "seed_kits/legacy_wrangling_v3/scripts/02_infer_missing_imaging_rows.py"])
    run(["python", "seed_kits/legacy_wrangling_v3/scripts/01_link.py"])
    run(["python", "-u", "seed_kits/legacy_wrangling_v3/scripts/02_enrich.py"])
    run(["python", "seed_kits/legacy_wrangling_v3/scripts/05_make_v9_compat_from_v3.py"])

    run([
        "python", "scripts/v9_backfill_legacy_slot_orientation.py",
        "--sheet-xlsx", str(imaging_sheet_xlsx),
        "--roi-csv", str(roi_csv_compat),
    ])

    run([
        "python", "scripts/v9_build_legacy_clutches_from_v9.py",
        "--csv", str(roi_csv_compat),
    ])

    run([
        "python", "scripts/v9_prepare_legacy_clutches_for_loader.py",
        "--in-csv", str(clutches_v9_in),
        "--out-csv", str(clutches_v9_for_loader),
    ])

    run([
        "python", "scripts/loader_legacy_clutches.py",
        "--csv", str(clutches_v9_for_loader),
        "--batch", "legacy_clutch_inference_v3",
    ])

    run([
        "python", "scripts/v9_load_imaging_legacy_rois.py",
        "--csv", str(roi_csv_compat),
    ])

    run([
        "python", "scripts/v9_load_imaging_clutch_memberships_from_v9.py",
        "--csv", str(memberships_v9),
    ])

    run([
        "python", "scripts/v10_build_legacy_treatments_from_v9.py",
        "--roi-csv", str(roi_csv_for_db),
        "--out-csv", str(repo / "seed_kits" / "2025-11-15-121231-autoload" / "treatments_v10.csv"),
    ])

    run([
        "python", "scripts/v10_load_treatments_from_csv.py",
        "--csv", str(repo / "seed_kits" / "2025-11-15-121231-autoload" / "treatments_v10.csv"),
    ])

    print("\n[OK] legacy imaging pipeline completed cleanly")


if __name__ == "__main__":
    main()
