from __future__ import annotations

import sys
from pathlib import Path

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.util import get_engine_from_env  # noqa: E402
from carp_app.etl.loader_imaging_legacy import load_imaging_from_legacy_standard  # noqa: E402
from carp_app.config.seed_kits import LEGACY_FINAL  # noqa: E402


def main() -> None:
    base = LEGACY_FINAL

    slots_csv = base / "legacy_imaging_slots.csv"
    rois_csv  = base / "legacy_imaging_rois.csv"

    engine = get_engine_from_env()
    print(f"DB_URL={engine.url}")
    print(f"[INFO] Loading LEGACY imaging from {slots_csv} and {rois_csv}")

    # CORRECT ARGUMENT ORDER: slots_csv, rois_csv, engine
    summary = load_imaging_from_legacy_standard(slots_csv, rois_csv, engine)
    print(f"[RESULT] imaging import summary: {summary}")
    print("[DONE] Legacy imaging import complete.")


if __name__ == "__main__":
    main()
