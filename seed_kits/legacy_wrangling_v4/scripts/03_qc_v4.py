from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKING = ROOT / "working"
QC = ROOT / "qc"
IN_DB = WORKING / "legacy_imaging_annotations_for_db_v9.csv"

def main() -> None:
    if not IN_DB.exists():
        raise SystemExit(f"missing DB CSV (run 02_enrich_v4.py first): {IN_DB}")

    QC.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(IN_DB, low_memory=False)

    print("DB_CSV", IN_DB)
    print("rows", len(df))

    if "roi_dir" not in df.columns:
        raise SystemExit("03_qc_v4.py: missing roi_dir column")

    print("unique_roi_dir", int(df["roi_dir"].nunique()))

    want = ["cams", "channels", "wavelengths_nm", "file_exts", "n_paths"]
    have = {c: (c in df.columns) for c in want}
    print("has_channel_cols", have)

    if all(have.values()):
        n_with_channels = int(df["channels"].notna().sum())
        n_total = len(df)
        print("n_with_channels", n_with_channels)
        print("pct_with_channels", round(100.0 * n_with_channels / max(n_total, 1), 3))

        out = QC / "qc_channel_coverage_v4.tsv"
        df_qc = pd.DataFrame([{
            "rows": n_total,
            "unique_roi_dir": int(df["roi_dir"].nunique()),
            "n_with_channels": n_with_channels,
            "pct_with_channels": 100.0 * n_with_channels / max(n_total, 1),
        }])
        df_qc.to_csv(out, sep="\t", index=False)
        print("WROTE", out)

if __name__ == "__main__":
    main()
