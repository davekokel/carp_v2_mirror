from __future__ import annotations

from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"
QC = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "qc"

IN_LOADER = WORK / "legacy_imaging_annotations_for_loader_v9_compat.csv"

OUT_DIST = QC / "qc_slots_per_plate_v4.tsv"
OUT_COUNTS = QC / "qc_plate_slot_counts_v4.tsv"
OUT_EXAMPLES = QC / "qc_plate_slot_examples_v4.tsv"

def _real(s: object) -> bool:
    if s is None:
        return False
    t = str(s).strip()
    return t != "" and t.lower() not in ("nan", "none", "na", "n/a", "<na>")

def main() -> None:
    if not IN_LOADER.exists():
        raise SystemExit(f"[STOP] missing: {IN_LOADER}")

    df = pd.read_csv(IN_LOADER, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    need = ["plate_date", "plate_id_filled", "slot_id_filled", "roi_dir", "bruker_roi_id"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"[STOP] loader compat missing columns: {missing}")

    plate_date = df["plate_date"].astype(str).str.replace(".0", "", regex=False).str.extract(r"(20\d{6})", expand=False)
    plate_id = pd.to_numeric(df["plate_id_filled"], errors="coerce").astype("Int64")
    slot_id = pd.to_numeric(df["slot_id_filled"], errors="coerce").astype("Int64")

    df2 = df.copy()
    df2["plate_code"] = plate_date.astype("string") + "-plate" + plate_id.astype("string")
    df2["slot_index"] = slot_id

    df2 = df2[df2["plate_code"].map(_real) & df2["slot_index"].notna()].copy()

    slot_counts = (
        df2.groupby("plate_code", as_index=False)
           .agg(
               n_slots=("slot_index", lambda s: int(pd.Series(s).nunique())),
               n_rois=("roi_dir", "count"),
               n_unique_roi_dir=("roi_dir", lambda s: int(pd.Series(s).nunique())),
           )
    )

    dist = (
        slot_counts.groupby("n_slots", as_index=False)
                   .agg(n_plates=("plate_code", "count"))
                   .sort_values("n_slots")
    )

    def _roi_base(s: object) -> str:
        t = "" if s is None else str(s).rstrip("/")
        return t.split("/")[-1] if t else ""

    examples = df2.copy()
    examples["roi_base"] = examples["roi_dir"].map(_roi_base)
    ex = (
        examples.groupby(["plate_code", "slot_index"], as_index=False)
                .agg(
                    n_rois=("roi_dir", "count"),
                    example_roi=("roi_base", "first"),
                )
    )
    ex = ex.merge(slot_counts[["plate_code", "n_slots"]], on="plate_code", how="left")
    ex = ex.sort_values(["n_slots", "plate_code", "slot_index"], ascending=[False, True, True]).head(400)

    QC.mkdir(parents=True, exist_ok=True)
    dist.to_csv(OUT_DIST, sep="\t", index=False)
    slot_counts.sort_values(["n_slots", "plate_code"], ascending=[False, True]).to_csv(OUT_COUNTS, sep="\t", index=False)
    ex.to_csv(OUT_EXAMPLES, sep="\t", index=False)

    print("[OK] IN_LOADER", IN_LOADER)
    print("[OK] plates", int(slot_counts["plate_code"].nunique()))
    print("[OK] wrote", OUT_DIST)
    print("[OK] wrote", OUT_COUNTS)
    print("[OK] wrote", OUT_EXAMPLES)
    print()
    print("SLOT_COUNT_DISTRIBUTION:")
    print(dist.to_string(index=False))

if __name__ == "__main__":
    main()
