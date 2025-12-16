from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKING = ROOT / "working"

IN_STRUCT = WORKING / "output_from_linking_v5.csv"
OUT_DB = WORKING / "legacy_imaging_annotations_for_db_v9.csv"

def main() -> None:
    if not IN_STRUCT.exists():
        raise SystemExit(f"missing structural CSV (run 01_link.py first): {IN_STRUCT}")
    raise SystemExit("02_enrich.py: TODO")

if __name__ == "__main__":
    main()
