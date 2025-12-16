from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WORKING = ROOT / "working"
QC = ROOT / "qc"

IN_DB = WORKING / "legacy_imaging_annotations_for_db_v9.csv"

def main() -> None:
    if not IN_DB.exists():
        raise SystemExit(f"missing DB CSV (run 02_enrich.py first): {IN_DB}")
    df = pd.read_csv(IN_DB, low_memory=False)
    print("DB_CSV", IN_DB)
    print("rows", len(df))
    if "roi_dir" in df.columns:
        print("unique_roi_dir", df["roi_dir"].nunique())
    else:
        raise SystemExit("03_qc.py: missing roi_dir column")
    raise SystemExit("03_qc.py: TODO (add QC checks + qc/ outputs)")

if __name__ == "__main__":
    main()
