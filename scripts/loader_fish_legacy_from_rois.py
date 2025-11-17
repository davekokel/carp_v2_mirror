from __future__ import annotations

import os
import pathlib
import sys

from sqlalchemy.engine import Engine
from sqlalchemy import create_engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _get_engine() -> Engine:
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL not set")
    return create_engine(db_url)

def main() -> None:
    print("loader_fish_legacy_from_rois.py: deprecated")
    print("No longer creating FSH_LEGACY_* rows in public.fish_instance.")
    print("Legacy imaging identity should live on imaging_slots/imaging_rois, not as synthetic fish codes.")
    _ = _get_engine()  # just to fail early if DB_URL is bad

if __name__ == "__main__":
    main()
