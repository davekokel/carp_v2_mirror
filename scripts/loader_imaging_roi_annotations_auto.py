from __future__ import annotations
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


BASE = Path(__file__).resolve().parents[1]
WORKING = BASE / "seed_kits" / "legacy_wrangling" / "working"
CSV_PATH = WORKING / "imaging_roi_annotations_AUTO.csv"


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL is not set in the environment")

    if not CSV_PATH.exists():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)

    engine = create_engine(db_url)

    with engine.begin() as cx:
        cx.execute(text("TRUNCATE TABLE public.imaging_roi_annotations"))

    df.to_sql(
        "imaging_roi_annotations",
        con=engine,
        schema="public",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )


if __name__ == "__main__":
    main()
