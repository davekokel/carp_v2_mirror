from __future__ import annotations

import argparse
import os
import sys
import pathlib
from typing import List, Dict, Any

import pandas as pd
from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine

# ---- repo bootstrap ---------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_BATCH_ID = "legacy_clutch_inference_2025-11-18"


def _load_legacy_clutches_csv(path: pathlib.Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"legacy clutches CSV not found: {path}")
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _prepare_payload(df: pd.DataFrame, batch: str) -> List[Dict[str, Any]]:
    required = {"clutch_code", "date_born", "roi_count"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"legacy_clutches.csv is missing required columns: {sorted(missing)}"
        )

    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        clutch_code = str(row["clutch_code"]).strip()
        if not clutch_code:
            continue

        date_born = row.get("date_born")
        clutch_date = None
        if pd.notna(date_born) and str(date_born).strip():
            clutch_date = str(date_born)

        roi_count = row.get("roi_count")
        try:
            egg_count = int(roi_count) if pd.notna(roi_count) else None
        except Exception:
            egg_count = None

        notes = f"legacy_imaging; roi_count={roi_count}"

        rows.append(
            {
                "clutch_code": clutch_code,
                "clutch_date": clutch_date,
                "estimated_egg_count": egg_count,
                "notes": notes,
                "source_system": "legacy_imaging",
                "import_batch_id": batch,
            }
        )

    return rows


def _upsert_clutches(engine: Engine, rows: List[Dict[str, Any]], batch: str) -> None:
    if not rows:
        print("[WARN] loader_legacy_clutches: no rows to insert.")
        return

    delete_memberships_sql = text(
        "DELETE FROM public.imaging_clutch_memberships"
    )

    delete_clutches_sql = text(
        """
        DELETE FROM public.clutches
        WHERE source_system = 'legacy_imaging'
          AND import_batch_id = :batch
        """
    )

    insert_sql = text(
        """
        INSERT INTO public.clutches (
          clutch_code,
          clutch_date,
          estimated_egg_count,
          notes,
          source_system,
          import_batch_id
        )
        VALUES (
          :clutch_code,
          :clutch_date,
          :estimated_egg_count,
          :notes,
          :source_system,
          :import_batch_id
        )
        """
    )

    with engine.begin() as cx:
        cx.execute(delete_memberships_sql)
        cx.execute(delete_clutches_sql, {"batch": batch})
        cx.execute(insert_sql, rows)

    print(
        f"[OK] Inserted {len(rows)} legacy clutch row(s) "
        f"for batch='{batch}'."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load inferred legacy clutches into public.clutches."
    )
    parser.add_argument(
        "--csv",
        default="seed_kits/legacy_wrangling/working/legacy_clutches.csv",
        help="Path to legacy_clutches.csv",
    )
    parser.add_argument(
        "--batch",
        default=DEFAULT_BATCH_ID,
        help="import_batch_id label to use for this load",
    )
    args = parser.parse_args()

    path = pathlib.Path(args.csv)
    df = _load_legacy_clutches_csv(path)
    rows = _prepare_payload(df, args.batch)

    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set.")
    print(f"DB_URL(loader_legacy_clutches)={db_url}")

    engine = create_engine(db_url)
    _upsert_clutches(engine, rows, args.batch)


if __name__ == "__main__":
    main()