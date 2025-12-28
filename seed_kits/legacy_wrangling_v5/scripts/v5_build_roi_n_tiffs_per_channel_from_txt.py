from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections import defaultdict, Counter
import re
import sys
import pandas as pd


IN_TXT_DEFAULT = Path("/Users/davekokel/Projects/carp_v2/seed_kits/legacy_wrangling_v5/raw/foundation_tiff_files_20251223_140835.txt")
OUT_CSV_DEFAULT = Path("/Users/davekokel/Projects/carp_v2/seed_kits/legacy_wrangling_v5/working/roi_n_tiffs_per_channel_v5.csv")

TIF_RX = re.compile(r"\.(tif|tiff)$", re.IGNORECASE)
CH_RXES = [
    re.compile(r"(?:^|[_\-\s\.])ch(?:annel)?\s*0*(\d+)(?:$|[_\-\s\.])", re.IGNORECASE),
    re.compile(r"(?:^|[_\-\s\.])c\s*0*(\d+)(?:$|[_\-\s\.])", re.IGNORECASE),
    re.compile(r"(?:^|[_\-\s\.])(405|445|458|488|514|532|561|594|633|640|647|660)(?:$|[_\-\s\.])", re.IGNORECASE),
]


def _parse_date_from_experiment_name(name: str) -> str:
    s = (name or "").strip()
    m = re.match(r"^(\d{8})", s)
    if not m:
        return ""
    try:
        d = datetime.strptime(m.group(1), "%Y%m%d").date()
        return d.isoformat()
    except Exception:
        return ""


def _channel_token(filename: str) -> str:
    fn = (filename or "").strip()
    if not fn:
        return ""
    for rx in CH_RXES:
        m = rx.search(fn)
        if m:
            return str(m.group(1))
    return ""


def _infer_foundation_and_experiment_and_roi(roi_dir: Path) -> tuple[str, str, str]:
    parts = list(roi_dir.parts)
    foundation = ""
    experiment = ""
    roi_label = roi_dir.name

    for key in ("Aang_Foundation", "Korra_Foundation"):
        if key in parts:
            foundation = key.replace("_Foundation", "")
            i = parts.index(key)
            if i + 1 < len(parts):
                experiment = parts[i + 1]
            break

    return (foundation, experiment, roi_label)


def build_counts(in_txt: Path) -> pd.DataFrame:
    if not in_txt.exists():
        raise SystemExit(f"[MISSING] {in_txt}")

    roi_counts: dict[str, Counter[str]] = defaultdict(Counter)
    tokens_seen: set[str] = set()

    with in_txt.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            s = raw.strip()
            if not s:
                continue
            if not TIF_RX.search(s):
                continue
            p = Path(s)
            roi_dir = p.parent
            tok = _channel_token(p.name)
            if tok:
                tokens_seen.add(tok)
            roi_counts[str(roi_dir)][tok] += 1

    def _tok_sort_key(t: str) -> tuple[int, str]:
        if not t:
            return (10**9, "")
        try:
            return (int(t), t)
        except Exception:
            return (10**8, t)

    tokens = sorted((t for t in tokens_seen if t), key=_tok_sort_key)

    rows = []
    for roi_path, c in roi_counts.items():
        roi_dir = Path(roi_path)
        foundation, experiment_name, roi_label = _infer_foundation_and_experiment_and_roi(roi_dir)
        experiment_date = _parse_date_from_experiment_name(experiment_name)

        row = {
            "foundation": foundation,
            "experiment_date": experiment_date,
            "experiment_name": experiment_name,
            "roi_label": roi_label,
            "roi_path": roi_path,
        }

        total = 0
        ch_present = []
        for t in tokens:
            n = int(c.get(t, 0))
            row[f"n_tiffs_ch_{t}"] = n
            if n > 0:
                ch_present.append(t)
            total += n

        row["n_tiffs_total"] = int(total)
        row["channels_key"] = ",".join(ch_present)
        rows.append(row)

    out = pd.DataFrame(rows)

    base_cols = ["foundation", "experiment_date", "experiment_name", "roi_label", "roi_path"]
    ch_cols = [f"n_tiffs_ch_{t}" for t in tokens]
    tail_cols = ["n_tiffs_total", "channels_key"]

    col_order = [c for c in base_cols if c in out.columns] + ch_cols + [c for c in tail_cols if c in out.columns]
    extra = [c for c in out.columns if c not in set(col_order)]
    out = out[col_order + extra]

    if "experiment_date" in out.columns:
        out = out.sort_values(
            by=["experiment_date", "experiment_name", "roi_label", "roi_path"],
            ascending=[False, False, True, True],
            na_position="last",
            kind="mergesort",
        )

    return out.reset_index(drop=True), tokens


def main() -> None:
    in_txt = Path(sys.argv[1]).expanduser() if len(sys.argv) >= 2 else IN_TXT_DEFAULT
    out_csv = Path(sys.argv[2]).expanduser() if len(sys.argv) >= 3 else OUT_CSV_DEFAULT

    out, tokens = build_counts(in_txt)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)

    print(f"[OK] input:  {in_txt}")
    print(f"[OK] output: {out_csv}")
    print(f"[OK] rows={len(out)} channel_cols={len(tokens)}")
    if tokens:
        print(f"[OK] channels: {','.join(tokens)}")


if __name__ == "__main__":
    main()
