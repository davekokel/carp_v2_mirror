from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_XLSX = RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
SHEET = "Master Imaging list"

OUT_XLSX = WORKING / "master_imaging_list_mountid_filled_v5.xlsx"
OUT_MAP = QC / "mount_id_fills_v5.tsv"
OUT_QC = QC / "mount_id_fills_v5.qc.tsv"

def _s(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if pd.isna(v):
        return ""
    return str(v).strip()

def norm_path(s: str) -> str:
    return str(s).strip().replace("\\", "/")

def is_blank(v) -> bool:
    t = _s(v)
    return (t == "") or (t.lower() in ("nan","none"))

def main() -> None:
    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)

    need = ["Data location", "date_mount", "mount_id"]
    for c in need:
        if c not in x.columns:
            raise SystemExit(f"[STOP] missing column in {SHEET}: {c}")

    sort_cols = [
        "Data location",
        "Unique Targets",
        "ZF female genotype",
        "ZF male genotype",
        "additional plasmids injected",
        "additional mRNAs injected",
        "additonal dye and chemicals",
        "free_text_label",
        "comments",
    ]
    for c in sort_cols:
        if c not in x.columns:
            x[c] = ""

    x = x.copy()
    x["Data_location_norm"] = x["Data location"].astype(str).map(norm_path)
    x["foundation_root"] = x["Data_location_norm"].str.extract(r"(Aang_Foundation|Korra_Foundation)")[0].fillna("")
    x["date_mount_dt"] = pd.to_datetime(x["date_mount"], errors="coerce")
    x["mount_id_str"] = x["mount_id"].apply(_s)

    fills = []
    filled_count = 0

    # KEY FIX: group by foundation_root + date_mount (day-unique), not data_location
    g = x.groupby(["foundation_root", x["date_mount_dt"].dt.date], dropna=False)

    for (fr, d), sub in g:
        if pd.isna(d) or fr == "":
            continue

        sub_idx = sub.index.tolist()

        # deterministic ordering for the entire day within a foundation
        order_df = x.loc[sub_idx, sort_cols].copy()
        for c in sort_cols:
            order_df[c] = order_df[c].apply(_s)
        order_df = order_df.sort_values(sort_cols, kind="mergesort")
        ordered_idx = order_df.index.tolist()

        # assign mount_id = 1..N for this day (only fill blanks; never overwrite existing)
        for pos, i in enumerate(ordered_idx, start=1):
            if is_blank(x.at[i, "mount_id_str"]):
                new_id = str(pos)
                x.at[i, "mount_id_str"] = new_id
                filled_count += 1
                fills.append({
                    "excel_row_1based": i + 2,
                    "foundation_root": fr,
                    "date_mount": str(x.at[i, "date_mount"]),
                    "old_mount_id": "",
                    "new_mount_id": new_id,
                    "data_location": x.at[i, "Data location"],
                    "reason": "day_unique_sorted_position",
                })

    x["mount_id"] = x["mount_id_str"]
    out_x = x.drop(columns=[c for c in ["Data_location_norm","foundation_root","date_mount_dt","mount_id_str"] if c in x.columns])

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as w:
        out_x.to_excel(w, sheet_name=SHEET, index=False)

    pd.DataFrame(fills).to_csv(OUT_MAP, sep="\t", index=False)
    pd.DataFrame([{
        "rows_total": int(len(x)),
        "rows_filled_mount_id": int(filled_count),
        "fill_events_logged": int(len(fills)),
        "note": "mount_id is unique within (foundation_root, date_mount) after this fill",
    }]).to_csv(OUT_QC, sep="\t", index=False)

    print(f"[OK] wrote {OUT_XLSX}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_MAP}")

if __name__ == "__main__":
    main()
