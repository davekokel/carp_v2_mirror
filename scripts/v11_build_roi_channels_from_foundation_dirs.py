from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Set, Dict, Tuple, List

import pandas as pd


_CAM_RE = re.compile(r'(?i)(?:^|[_/])(cama|camb)(?=[_/\.]|$)')
_CH_RE  = re.compile(r'(?i)(?:^|[_/])ch(\d+)(?=[_/\.]|$)')
_NM_RE  = re.compile(r'(?i)(?:^|[_/])(\d{3})nm(?=[_/\.]|$)')


def _canon_cam(s: str) -> str:
    s2 = s.lower()
    if s2 == "cama":
        return "CamA"
    if s2 == "camb":
        return "CamB"
    return s


def _roi_root_from_path(p: str) -> Tuple[str, str, str] | None:
    # Expected: Foundation/ExperimentKey/ROIroot/...
    parts = p.strip().lstrip("./").split("/")
    if len(parts) < 3:
        return None
    foundation = parts[0]
    experiment_key = parts[1]
    roi_root = "/".join(parts[0:3])
    return foundation, experiment_key, roi_root


def _extract_tokens(p: str) -> Tuple[Set[str], Set[str], Set[int], Set[str]]:
    cams: Set[str] = set(_canon_cam(m.group(1)) for m in _CAM_RE.finditer(p))
    chs: Set[str] = set(f"ch{int(m.group(1))}" for m in _CH_RE.finditer(p))
    nms: Set[int] = set(int(m.group(1)) for m in _NM_RE.finditer(p))

    # file extensions: capture last suffix; treat ".zarr" as an extension
    name = Path(p).name
    ext = Path(name).suffix.lower()
    exts: Set[str] = set([ext]) if ext else set()

    return cams, chs, nms, exts


def main() -> None:
    RAW = Path("seed_kits/legacy_wrangling_v4/raw/2025-12-22-161855-foundation_dirs_depth6.txt")
    OUT = Path("seed_kits/legacy_wrangling_v4/working") / f"{pd.Timestamp.now().strftime('%Y-%m-%d-%H%M%S')}-roi_channels_by_roi_root.tsv"

    rows: List[Dict[str, object]] = []

    for line in RAW.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s:
            continue

        key = _roi_root_from_path(s)
        if key is None:
            continue
        foundation, experiment_key, roi_root = key

        cams, chs, nms, exts = _extract_tokens(s)

        rows.append(
            {
                "foundation": foundation,
                "experiment_key": experiment_key,
                "roi_root": roi_root,
                "cams": ";".join(sorted(cams)),
                "channels": ";".join(sorted(chs, key=lambda z: int(z[2:]))),
                "wavelengths_nm": ";".join(str(x) for x in sorted(nms)),
                "file_exts": ";".join(sorted(exts)),
                "path": s,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("[STOP] no rows parsed; check RAW path and format")

    g = (
        df.groupby(["foundation", "experiment_key", "roi_root"], as_index=False)
          .agg(
              cams=("cams", lambda x: ";".join(sorted({t for v in x for t in str(v).split(";") if t}))),
              channels=("channels", lambda x: ";".join(sorted({t for v in x for t in str(v).split(";") if t}, key=lambda z: int(z[2:]) if z.startswith("ch") and z[2:].isdigit() else 9999))),
              wavelengths_nm=("wavelengths_nm", lambda x: ";".join(str(i) for i in sorted({int(t) for v in x for t in str(v).split(";") if t.isdigit()}))),
              file_exts=("file_exts", lambda x: ";".join(sorted({t for v in x for t in str(v).split(";") if t}))),
              n_paths=("path", "count"),
          )
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    g.sort_values(["foundation", "experiment_key", "roi_root"]).to_csv(OUT, sep="\t", index=False)

    print("[OK] wrote:", OUT)
    print("[OK] roi_roots:", len(g))

    # quick sanity check on your example
    ex = "Aang_Foundation/20251204_cdk_sensor_red_mem_red_nuc/fish1_24hpf_roi1"
    hit = g[g["roi_root"] == ex]
    if len(hit):
        r = hit.iloc[0].to_dict()
        print("[CHECK]", ex, "channels=", r.get("channels"), "wavelengths_nm=", r.get("wavelengths_nm"), "cams=", r.get("cams"))
    else:
        print("[CHECK] did not find expected roi_root:", ex)


if __name__ == "__main__":
    main()
