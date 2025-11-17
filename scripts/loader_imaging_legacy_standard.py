#!/usr/bin/env python
from __future__ import annotations

import sys
import pathlib
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.loaders import get_engine_from_env
from carp_app.etl.loader_imaging_legacy import load_imaging_from_legacy_standard


def main(argv: list[str] | None = None) -> int:
    base = Path("seed_kits/standard_from_legacy")
    slots_csv = base / "imaging_slots_standard_from_legacy.csv"
    rois_csv = base / "imaging_rois_standard_from_legacy.csv"

    engine = get_engine_from_env()
    print(f"DB_URL={engine.url}")

    summary = load_imaging_from_legacy_standard(slots_csv, rois_csv, engine=engine)
    print(f"Loaded imaging slots/rois from {slots_csv} and {rois_csv}")
    print(f"  slot_rows:      {summary['slot_rows']}")
    print(f"  slots_inserted: {summary['slots_inserted']}")
    print(f"  roi_rows:       {summary['roi_rows']}")
    print(f"  rois_inserted:  {summary['rois_inserted']}")
    if summary["warnings"]:
        print("  Warnings:")
        for w in summary["warnings"]:
            print(f"    - {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
