from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

CLUSTER_PREFIX = "/clusterfs/vast/abcabc/"

_RX_ROI_SEG = re.compile(r"roi\d+", re.I)
_RX_FISH_SEG = re.compile(r"^fish\d+[_\-]", re.I)

def _s(x: object) -> str:
    if x is None:
        return ""
    return str(x).strip()

def _to_posix(p: str) -> str:
    p = _s(p)
    if not p:
        return ""
    return p.replace("\\", "/").replace("//", "/")

def _to_cluster_path_from_tiff_list(line: str) -> str:
    t = _to_posix(line).lstrip("/")
    if not t:
        return ""
    if t.startswith("Aang_Foundation/") or t.startswith("Korra_Foundation/"):
        return CLUSTER_PREFIX + t
    if t.startswith("abcabc/Aang_Foundation/") or t.startswith("abcabc/Korra_Foundation/"):
        return CLUSTER_PREFIX + t.split("abcabc/", 1)[1]
    if t.startswith(CLUSTER_PREFIX.lstrip("/")):
        return "/" + t
    if t.startswith(CLUSTER_PREFIX):
        return t
    return ""

def _foundation_from_cluster_path(p: str) -> str:
    t = _s(p)
    if "/Aang_Foundation/" in t:
        return "aang"
    if "/Korra_Foundation/" in t:
        return "korra"
    return ""

def _dataset_slug_from_cluster_path(p: str) -> str:
    t = _s(p)
    m = re.search(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)/", t)
    if not m:
        return ""
    return m.group(2).strip()

def _to_windows_from_cluster(p: str) -> str:
    t = _s(p)
    if not t.startswith(CLUSTER_PREFIX):
        return ""
    rel = t[len(CLUSTER_PREFIX):].replace("/", "\\")
    return "X:\\abcabc\\" + rel

def _roi_dir_from_cluster_file_path(fp: str) -> str:
    p = _to_posix(fp)
    if not p.startswith(CLUSTER_PREFIX):
        return ""
    parts = [x for x in p.split("/") if x]
    if len(parts) < 6:
        return ""
    try:
        i_fnd = parts.index("abcabc") + 1
    except ValueError:
        return ""
    fnd = parts[i_fnd]
    if fnd not in ("Aang_Foundation", "Korra_Foundation"):
        return ""

    idx_last = len(parts) - 1
    if "." in parts[idx_last]:
        dir_parts = parts[:-1]
    else:
        dir_parts = parts[:]

    roi_idx = None
    for i in range(len(dir_parts) - 1, 0, -1):
        if _RX_ROI_SEG.search(dir_parts[i]):
            roi_idx = i
            break
    if roi_idx is not None:
        return "/" + "/".join(dir_parts[: roi_idx + 1])

    fish_idx = None
    for i in range(len(dir_parts) - 1, 0, -1):
        if _RX_FISH_SEG.search(dir_parts[i]) or dir_parts[i].lower().startswith("fish"):
            fish_idx = i
            break
    if fish_idx is not None:
        return "/" + "/".join(dir_parts[: fish_idx + 1])

    return "/" + "/".join(dir_parts[: i_fnd + 2])

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--tiff-list",
        default="seed_kits/legacy_wrangling_v4/raw/foundation_tiff_files_20251223_140835.txt",
    )
    ap.add_argument(
        "--out",
        default="seed_kits/legacy_wrangling_v4/working/ideal_roi_universe_v4.tsv",
    )
    args = ap.parse_args()

    tiff_list = Path(args.tiff_list)
    out = Path(args.out)

    if not tiff_list.exists():
        raise SystemExit(f"[STOP] missing tiff list: {tiff_list}")

    roi_dirs: set[str] = set()

    with tiff_list.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cluster_fp = _to_cluster_path_from_tiff_list(line)
            if not cluster_fp:
                continue
            rd = _roi_dir_from_cluster_file_path(cluster_fp)
            if rd:
                roi_dirs.add(rd.rstrip("/"))

    roi_dirs = sorted(roi_dirs)

    df = pd.DataFrame(
        {
            "roi_path": roi_dirs,
        }
    )
    df["windows_path"] = df["roi_path"].map(_to_windows_from_cluster)
    df["foundation"] = df["roi_path"].map(_foundation_from_cluster_path)
    df["dataset_slug"] = df["roi_path"].map(_dataset_slug_from_cluster_path)

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, sep="\t", index=False)
    print(str(out))
    print("[QC] roi_dirs", len(df))

if __name__ == "__main__":
    main()
