from __future__ import annotations

import sys
from pathlib import Path

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.loaders import (   # noqa: E402
    get_engine_from_env,
    load_plasmids_from_csv,
    load_rnas_from_csv,
)
from carp_app.config.seed_kits import LEGACY_FINAL  # noqa: E402


def main() -> None:
    base = LEGACY_FINAL

    plasmids_csv = base / "legacy_plasmids.csv"
    rnas_csv = base / "legacy_rnas.csv"

    engine = get_engine_from_env()

    print(f"DB_URL={engine.url}")
    print(f"[INFO] Loading LEGACY plasmids from {plasmids_csv}")
    pl_summary = load_plasmids_from_csv(plasmids_csv, engine=engine)
    print(f"[RESULT] plasmids: {pl_summary}")

    print(f"[INFO] Loading LEGACY rnas from {rnas_csv}")
    rna_summary = load_rnas_from_csv(rnas_csv, engine=engine)
    print(f"[RESULT] rnas: {rna_summary}")

    print("[DONE] Legacy constructs import complete.")


if __name__ == "__main__":
    main()
