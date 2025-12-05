#!/usr/bin/env python
from __future__ import annotations

import os
import sys
import pathlib
from typing import Any, Dict

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.argv:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.fish_v11_shared import load_fish_from_csv  # new canonical loader


def _eng() -> Engine:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL environment variable is not set. Run scripts/use_db.sh first.")
    return create_engine(db_url)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: v11_seed_fish_from_csv.py /path/to/fish.csv", file=sys.stderr)
        return 1

    csv_path = pathlib.Path(argv[1])
    if not csv_path.is_file():
        print(f"[ERROR] CSV not found: {csv_path}", file=sys.stderr)
        return 1

    df = pd.read_csv(csv_path)
    print(f"[INFO] Read {len(df)} row(s) from {csv_path}")

    eng = _eng()
    summary: Dict[str, Any]
    with eng.begin() as cx:
        summary = load_fish_from_csv(df, cx)

    print(
        "[OK] v11 fish import complete — "
        f"instances={summary.get('n_instances', 0)}, "
        f"tanks={summary.get('n_tanks', 0)}, "
        f"lines_created={summary.get('n_lines_created', 0)}, "
        f"lines_reused={summary.get('n_lines_reused', 0)}"
    )

    rej = summary.get("rejected_rows")
    if isinstance(rej, pd.DataFrame) and not rej.empty:
        print(f"[WARN] {len(rej)} row(s) were rejected during import.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
