from __future__ import annotations

import sys
import re
from pathlib import PurePosixPath, Path
from collections import Counter

TIF_RX = re.compile(r"\.(tif|tiff)$", re.IGNORECASE)

BOUND_L = r"(^|[^A-Za-z0-9])"
BOUND_R = r"([^A-Za-z0-9]|$)"

CAM_RX  = re.compile(BOUND_L + r"Cam([A-Za-z0-9]+)" + BOUND_R, re.IGNORECASE)
CH_RX   = re.compile(BOUND_L + r"ch(\d+)"          + BOUND_R, re.IGNORECASE)
CAMN_RX = re.compile(BOUND_L + r"CAM(\d+)"         + BOUND_R, re.IGNORECASE)
WL_RX   = re.compile(BOUND_L + r"(\d{3})nm"        + BOUND_R, re.IGNORECASE)

ROI_PART_RX = re.compile(r"(?:^|[_\-])roi(\d+)\b", re.IGNORECASE)

DERIVED_PATH_RX = re.compile(r"(^|/)(fft|mips|central_slices|psfgen|psf|background|chromatic|denoising|otf)(/|$)", re.IGNORECASE)
MIP_NAME_RX = re.compile(r"(?:^|[_\-])mip(?:[_\-]|\.|$)|[_\-]mip_[xyz](?:[_\-]|\.|$)", re.IGNORECASE)


def _norm(s: str) -> str:
    return s.strip().lower()


def _g(rx: re.Pattern[str], name: str) -> str | None:
    m = rx.search(name)
    if not m:
        return None
    return m.group(2)  # because of (BOUND_L)(TOKEN)(BOUND_R)


def channel_name_from_filename(name: str) -> str:
    cam  = _g(CAM_RX, name)
    ch   = _g(CH_RX, name)
    camn = _g(CAMN_RX, name)
    wl   = _g(WL_RX, name)

    cam_v  = f"cam{_norm(cam)}" if cam else "-"
    ch_v   = f"ch{_norm(ch)}" if ch else "-"
    camn_v = f"cam{_norm(camn)}" if camn else "-"
    wl_v   = _norm(wl) if wl else "-"

    return f"{cam_v}-{ch_v}-{camn_v}-{wl_v}"


def has_any_channel_tokens(name: str) -> bool:
    return bool(CAM_RX.search(name) or CH_RX.search(name) or CAMN_RX.search(name) or WL_RX.search(name))


def roi_root_from_path(p: PurePosixPath) -> str:
    parts = list(p.parts)
    for i in range(len(parts) - 1, -1, -1):
        if ROI_PART_RX.search(parts[i]):
            return str(PurePosixPath(*parts[: i + 1]))
    return str(p.parent)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python v5_build_roi_channel_counts_from_txt.py /path/to/foundation_tiff_files_*.txt [out_csv]")

    in_txt = Path(sys.argv[1]).expanduser()
    out_csv = Path(sys.argv[2]).expanduser() if len(sys.argv) >= 3 else Path(
        "/Users/davekokel/Projects/carp_v2/seed_kits/legacy_wrangling_v5/working/roi_channel_counts_v5.csv"
    )

    counts: Counter[tuple[str, str]] = Counter()
    n_lines = 0
    n_tiffs = 0
    n_used = 0

    with open(in_txt, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            n_lines += 1
            s = line.strip()
            if not s:
                continue
            if not TIF_RX.search(s):
                continue

            n_tiffs += 1
            p = s.replace("\\", "/")

            if DERIVED_PATH_RX.search(p):
                continue

            pp = PurePosixPath(p)
            name = pp.name

            if MIP_NAME_RX.search(name):
                continue

            if not has_any_channel_tokens(name):
                continue

            roi_path = roi_root_from_path(pp)
            chname = channel_name_from_filename(name)

            counts[(roi_path, chname)] += 1
            n_used += 1

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="\n") as out:
        out.write("roi_path,channel_name,n_tiffs\n")
        for (roi_path, chname), n in sorted(counts.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            out.write(f"{roi_path},{chname},{n}\n")

    print(f"[OK] input:  {in_txt}")
    print(f"[OK] output: {out_csv}")
    print(f"[OK] lines={n_lines} tiffs={n_tiffs} used={n_used} rows={len(counts)}")


if __name__ == "__main__":
    main()
