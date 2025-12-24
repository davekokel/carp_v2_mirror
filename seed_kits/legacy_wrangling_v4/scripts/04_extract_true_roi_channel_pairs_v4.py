from __future__ import annotations

import re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]

IN_LIST = ROOT / "seed_kits" / "legacy_wrangling_v4" / "raw" / "2025-12-22-161855-foundation_dirs_depth6.txt"
OUT = ROOT / "seed_kits" / "legacy_wrangling_v4" / "working" / "roi_channel_pairs_true.tsv"

CLUSTER_PREFIX = "/clusterfs/vast/abcabc/"

RE_TRIPLE = re.compile(r"(CamA|CamB)_ch(\d+).*?_(\d{3})nm", re.IGNORECASE)
RE_ROI_ROOT = re.compile(r"^(Aang_Foundation|Korra_Foundation)/(\d{8}[^/]+)/([^/]+)(?:/|$)")

def main() -> None:
    if not IN_LIST.exists():
        raise SystemExit(f"[STOP] missing: {IN_LIST}")

    rows = []
    with IN_LIST.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip().lstrip("./")
            if not s:
                continue

            m_root = RE_ROI_ROOT.match(s)
            if not m_root:
                continue

            m_tri = RE_TRIPLE.search(s)
            if not m_tri:
                continue

            foundation_long = m_root.group(1)
            experiment_key = m_root.group(2)
            roi_folder = m_root.group(3)

            roi_root_rel = f"{foundation_long}/{experiment_key}/{roi_folder}"
            roi_path = CLUSTER_PREFIX + roi_root_rel

            cam = m_tri.group(1)
            ch = int(m_tri.group(2))
            nm = int(m_tri.group(3))

            rows.append(
                {
                    "foundation_long": foundation_long,
                    "experiment_key": experiment_key,
                    "roi_root_rel": roi_root_rel,
                    "roi_path": roi_path,
                    "cam": cam,
                    "channel": f"ch{ch}",
                    "wavelength_nm": nm,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("[STOP] no filename-level (CamX_chY_###nm) hits found in snapshot")

    g = (
        df.groupby(
            ["foundation_long", "experiment_key", "roi_root_rel", "roi_path", "cam", "channel", "wavelength_nm"],
            as_index=False,
        )
        .size()
        .rename(columns={"size": "n_hits"})
        .sort_values(["foundation_long", "experiment_key", "roi_root_rel", "cam", "channel", "wavelength_nm"])
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    g.to_csv(OUT, sep="\t", index=False)

    print("[OK] wrote:", OUT)
    print("[OK] roi_paths_with_any_triple:", int(g["roi_path"].nunique()))
    print("[OK] unique_triples:", int(g[["cam", "channel", "wavelength_nm"]].drop_duplicates().shape[0]))
    print("[OK] total_rows:", len(g))

if __name__ == "__main__":
    main()
