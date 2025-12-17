from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]

IN_ROI_XLSX = REPO_ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw" / "2025-11-13-092338-korra_aang_roi_root_tiffs_good-3.xlsx"
IN_VOCAB = REPO_ROOT / "seed_kits" / "legacy_wrangling_v3" / "working" / "qc_hint_mining" / "token_vocab_v1.csv"

OUT_DIR = REPO_ROOT / "seed_kits" / "legacy_wrangling_v3" / "working" / "qc_hint_mining"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / "roi_typed_hints_v1.csv"

def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a")

def parse_roi_dir(roi_dir: str) -> dict[str, str | None]:
    if not _nonempty(roi_dir):
        return {"foundation": None, "experiment_folder": None, "fish_folder": None, "roi_folder": None}
    s = str(roi_dir)
    m = re.search(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)/([^/]+)/([^/]+)$", s)
    if not m:
        return {"foundation": None, "experiment_folder": None, "fish_folder": None, "roi_folder": None}
    foundation = "aang" if m.group(1) == "Aang_Foundation" else "korra"
    return {
        "foundation": foundation,
        "experiment_folder": m.group(2),
        "fish_folder": m.group(3),
        "roi_folder": m.group(4),
    }

def tokenize(*parts: str | None) -> list[str]:
    toks: list[str] = []
    for p in parts:
        if not _nonempty(p):
            continue
        s = str(p).strip().lower()
        s = s.replace("-", "_")
        s = re.sub(r"[^a-z0-9_]+", "_", s)
        for t in s.split("_"):
            t = t.strip()
            if t:
                toks.append(t)
    return toks

def uniq_join(items: list[str]) -> str:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return "|".join(out) if out else ""

def main() -> None:
    if not IN_ROI_XLSX.exists():
        raise SystemExit(f"missing ROI xlsx: {IN_ROI_XLSX}")
    if not IN_VOCAB.exists():
        raise SystemExit(f"missing vocab: {IN_VOCAB}")

    vocab = pd.read_csv(IN_VOCAB)
    if not {"token", "meaning_type"} <= set(vocab.columns):
        raise SystemExit("vocab missing required columns: token, meaning_type")

    tok2type = dict(zip(vocab["token"].astype(str).str.strip().str.lower(), vocab["meaning_type"].astype(str).str.strip()))

    roi = pd.read_excel(IN_ROI_XLSX)
    if "roi_dir" not in roi.columns:
        raise SystemExit("ROI xlsx missing roi_dir column")

    rows = []
    for rd in roi["roi_dir"].dropna().astype(str):
        parsed = parse_roi_dir(rd)
        toks = tokenize(parsed["experiment_folder"], parsed["fish_folder"], parsed["roi_folder"])

        typed = {
            "organelle": [],
            "fluor": [],
            "anatomy": [],
            "developmental_stage": [],
            "experiment_label": [],
        }

        matched = []
        for t in toks:
            mt = tok2type.get(t)
            if mt in typed:
                typed[mt].append(t)
                matched.append(t)

        rows.append({
            "roi_dir": rd,
            "foundation": parsed["foundation"],
            "experiment_folder": parsed["experiment_folder"],
            "fish_folder": parsed["fish_folder"],
            "roi_folder": parsed["roi_folder"],
            "tokens_all": uniq_join(toks),
            "tokens_matched": uniq_join(matched),
            "organelle_hints": uniq_join(typed["organelle"]),
            "fluor_hints": uniq_join(typed["fluor"]),
            "anatomy_hints": uniq_join(typed["anatomy"]),
            "dev_stage_hints": uniq_join(typed["developmental_stage"]),
            "experiment_label_hints": uniq_join(typed["experiment_label"]),
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)

    print("WROTE", OUT_CSV)
    print("ROWS", len(out), "UNIQUE_ROI_DIR", out["roi_dir"].nunique())
    print("COVERAGE tokens_matched nonempty", int((out["tokens_matched"].astype(str).str.strip() != "").sum()))
    for c in ["organelle_hints","fluor_hints","anatomy_hints","dev_stage_hints"]:
        vc = out[c].astype(str).replace({"": pd.NA}).dropna().value_counts().head(20)
        print("\n", c)
        print(vc.to_string())

if __name__ == "__main__":
    main()
