import pandas as pd
from pathlib import Path

PATH = Path("seed_kits/legacy_wrangling/working/roi_all_markers_flat_working.csv")

df = pd.read_csv(PATH)

parent_cols = [c for c in df.columns if "parent" in c.lower() or "mom" in c.lower() or "dad" in c.lower()]

print("Parent-ish columns:", parent_cols)

missing_mask = df[parent_cols].isna().any(axis=1) if parent_cols else df.index == -1

print(f"Total rows: {len(df)}")
print(f"Rows with any missing parent fields: {missing_mask.sum()}")

if missing_mask.sum() > 0:
    print("\nSample rows with missing parent info:")
    print(df.loc[missing_mask].head(20).to_string(index=False))
