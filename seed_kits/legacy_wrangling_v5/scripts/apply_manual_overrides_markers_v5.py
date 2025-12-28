from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_BASE = WORKING / "roi_path_to_session_markers_v5.csv"
IN_OVR = WORKING / "manual_overrides_markers_v5.tsv"

OUT = WORKING / "roi_path_to_session_markers_v5_manual.csv"
OUT_LOG = QC / "roi_path_to_session_markers_v5_manual.log.tsv"
OUT_QC = QC / "roi_path_to_session_markers_v5_manual.qc.tsv"

COLS = [
    "genotype_base_codes",
    "genotype_allele_codes",
    "treatment_rna_base_codes",
    "treatment_plasmid_base_codes",
]

def _s(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    return str(v).strip()

def is_blank(v) -> bool:
    t = _s(v)
    return t == "" or t.lower() in ("nan", "none")

def main() -> None:
    for p in (IN_BASE, IN_OVR):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    base = pd.read_csv(IN_BASE)
    if "roi_path" not in base.columns:
        raise SystemExit("[STOP] base file missing roi_path")

    ovr = pd.read_csv(IN_OVR, sep="\t")
    need = {"roi_path"} | set(COLS)
    miss = sorted(list(need - set(ovr.columns)))
    if miss:
        raise SystemExit(f"[STOP] overrides file missing columns: {miss}")

    base = base.copy()
    base["_row"] = range(len(base))
    ovr = ovr.copy()

    # merge to locate rows
    m = base.merge(ovr, on="roi_path", how="left", suffixes=("", "_ovr"))

    logs = []
    changed = 0

    for col in COLS:
        ocol = f"{col}_ovr"
        if ocol not in m.columns:
            continue

        # only apply where base is blank and override is nonblank
        mask = m[col].apply(is_blank) & m[ocol].apply(lambda v: not is_blank(v))
        if mask.any():
            for _, r in m.loc[mask, ["roi_path", col, ocol, "_row"]].iterrows():
                logs.append({
                    "roi_path": r["roi_path"],
                    "field": col,
                    "old": _s(r[col]),
                    "new": _s(r[ocol]),
                    "mode": "fill_blank_only",
                })
            base.loc[m.loc[mask, "_row"], col] = m.loc[mask, ocol].astype(str).values
            changed += int(mask.sum())

    base.drop(columns=["_row"]).to_csv(OUT, index=False)
    pd.DataFrame(logs).to_csv(OUT_LOG, sep="\t", index=False)
    pd.DataFrame([{
        "rows_total": int(len(base)),
        "override_rows": int(len(ovr)),
        "fields_written": int(changed),
        "output": str(OUT),
    }]).to_csv(OUT_QC, sep="\t", index=False)

    print(f"[OK] wrote {OUT} rows={len(base)}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_LOG}")

if __name__ == "__main__":
    main()
