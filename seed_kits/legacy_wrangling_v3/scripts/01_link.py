from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw"
WORKING = ROOT / "working"

ROI_XLSX = RAW / "2025-11-13-092338-korra_aang_roi_root_tiffs_good-3.xlsx"
IMAGING_XLSX = RAW / "2025-11-21-220012-imaging_sheet.xlsx"
OUT = WORKING / "output_from_linking_v5.csv"

def main() -> None:
    if not ROI_XLSX.exists():
        raise SystemExit(f"missing ROI xlsx: {ROI_XLSX}")
    if not IMAGING_XLSX.exists():
        raise SystemExit(f"missing imaging sheet xlsx: {IMAGING_XLSX}")

    df_roi = pd.read_excel(ROI_XLSX)
    df_img = pd.read_excel(IMAGING_XLSX)

    print("ROI_XLSX", ROI_XLSX)
    print("IMAGING_XLSX", IMAGING_XLSX)
    print("roi_rows", len(df_roi), "roi_cols", len(df_roi.columns))
    print("imaging_rows", len(df_img), "imaging_cols", len(df_img.columns))

    raise SystemExit("01_link.py: TODO (verifier step needed before implementing mapping)")

if __name__ == "__main__":
    main()
