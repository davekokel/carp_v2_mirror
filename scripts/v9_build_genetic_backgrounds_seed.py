from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


def norm_code(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).strip()


def main() -> None:
    ROOT = Path(__file__).resolve().parents[1]
    # use the autoload seed kit location
    base = ROOT / "seed_kits" / "2025-11-15-121231-autoload"

    xlsx_path = base / "genetic_backgrounds.xlsx"
    if not xlsx_path.exists():
        raise SystemExit(f"genetic_backgrounds.xlsx not found at {xlsx_path}")

    df = pd.read_excel(xlsx_path)
    print(f"[v9_build_genetic_backgrounds_seed] read {len(df)} row(s) from {xlsx_path}")

    required = ["name", "alias"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"genetic_backgrounds.xlsx missing columns {missing}; found {list(df.columns)}")

    df = df.copy()
    df["name"]  = df["name"].astype(str)
    df["alias"] = df["alias"].astype(str).where(~df["alias"].isna(), "")

    rows = []

    for _, row in df.iterrows():
        primary = norm_code(row["name"])
        alias   = norm_code(row["alias"])

        if not primary:
            continue

        # primary background
        rows.append({
            "bg_code": primary,
            "bg_name": primary,
            "bg_category": "core",
            "source_system": "standard_seedkit",
            "description": "",
        })

        # optional alias (if present)
        if alias and alias != primary:
            rows.append({
                "bg_code": alias,
                "bg_name": alias,
                "bg_category": "alias_of_" + primary,
                "source_system": "standard_seedkit",
                "description": f"Alias for background '{primary}'",
            })

    if not rows:
        print("[v9_build_genetic_backgrounds_seed] no usable rows; exiting.")
        return

    seed_df = pd.DataFrame(rows).drop_duplicates(subset=["bg_code"]).reset_index(drop=True)

    out_dir = base / "working"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "genetic_backgrounds_seed.csv"

    seed_df.to_csv(out_path, index=False)
    print(f"[v9_build_genetic_backgrounds_seed] wrote {len(seed_df)} row(s) to {out_path}")


if __name__ == "__main__":
    main()
