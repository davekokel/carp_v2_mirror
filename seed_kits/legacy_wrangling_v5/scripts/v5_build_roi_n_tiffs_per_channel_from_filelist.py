from __future__ import annotations

import re
from pathlib import Path
import pandas as pd

IN_TXT = Path("/Users/davekokel/Projects/carp_v2/seed_kits/legacy_wrangling_v5/raw/foundation_tiff_files_20251223_140835.txt")

OUT_CSV = Path("seed_kits/legacy_wrangling_v5/working/roi_n_tiffs_per_channel_v5.csv")

TIF_RE = re.compile(r"\.(tif|tiff)$", re.IGNORECASE)

CHANNEL_PATTERNS = [
    re.compile(r"(?:^|[_\-\s\.])ch(?:annel)?\s*0*(\d+)(?:$|[_\-\s\.])", re.IGNORECASE),
    re.compile(r"(?:^|[_\-\s\.])c\s*0*(\d+)(?:$|[_\-\s\.])", re.IGNORECASE),
    re.compile(r"(?:^|[_\-\s\.])(405|445|458|488|514|532|561|594|633|640|647|660)(?:$|[_\-\s\.])", re.IGNORECASE),
]

def _channel_token(filename: str) -> str:
    s = filename.strip()
    if not s:
        return ""
    for rx in CHANNEL_PATTERNS:
        m = rx.search(s)
        if m:
            return m.group(1)
    return ""

def main() -> None:
    if not IN_TXT.exists():
        raise SystemExit(f"[STOP] missing input: {IN_TXT}")

    lines = IN_TXT.read_text(encoding="utf-8", errors="ignore").splitlines()
    files = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if not TIF_RE.search(s):
            continue
        files.append(s)

    if not files:
        raise SystemExit("[STOP] no .tif/.tiff file paths found in input txt")

    rows = []
    for fp in files:
        p = Path(fp)
        roi_path = str(p.parent)
        ch = _channel_token(p.name)
        rows.append({"roi_path": roi_path, "file_path": str(p), "channel": ch})

    df = pd.DataFrame(rows)

    ch_present = sorted(
        [c for c in df["channel"].dropna().astype(str).unique().tolist() if c.strip()],
        key=lambda x: (len(x), x),
    )

    g = df.groupby("roi_path", dropna=False)
    out = pd.DataFrame({"roi_path": list(g.groups.keys())})

    total = g.size().rename("n_tiffs_total")
    out = out.merge(total, left_on="roi_path", right_index=True, how="left")

    if ch_present:
        for ch in ch_present:
            s = (df["channel"].astype(str) == ch)
            cnt = df[s].groupby("roi_path").size().rename(f"n_tiffs_ch_{ch}")
            out = out.merge(cnt, left_on="roi_path", right_index=True, how="left")

    for c in out.columns:
        if c.startswith("n_tiffs_"):
            out[c] = out[c].fillna(0).astype(int)

    def _channels_key(r) -> str:
        parts = []
        for ch in ch_present:
            col = f"n_tiffs_ch_{ch}"
            if col in out.columns and int(r[col]) > 0:
                parts.append(ch)
        return ",".join(parts)

    out["channels_key"] = out.apply(_channels_key, axis=1)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out = out.sort_values(["roi_path"]).reset_index(drop=True)
    out.to_csv(OUT_CSV, index=False)

    print(f"[OK] wrote {OUT_CSV} rows={len(out)} files={len(files)} channels={len(ch_present)}")
    print("[COLS]", ", ".join(out.columns.tolist()))

if __name__ == "__main__":
    main()
