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
    return (t == "") or (t.lower() == "nan") or (t.lower() == "none")

def main() -> None:
    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)

    # required cols
    need = ["Data location", "date_mount", "mount_id"]
    for c in need:
        if c not in x.columns:
            raise SystemExit(f"[STOP] missing column in {SHEET}: {c}")

    # ensure optional cols exist for deterministic sorting
    sort_cols = [
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

    # group by the “session bucket”
    g = x.groupby(["foundation_root", "Data_location_norm", x["date_mount_dt"].dt.date], dropna=False)

    for (fr, dl, d), sub in g:
        if pd.isna(d) or dl == "" or fr == "":
            continue

        sub_idx = sub.index.tolist()

        # If all have mount_id, nothing to do
        cur = x.loc[sub_idx, "mount_id_str"].tolist()
        if all(not is_blank(v) for v in cur):
            continue

        # Determine which rows need filling
        to_fill = [i for i in sub_idx if is_blank(x.at[i, "mount_id_str"])]

        # If group has exactly one row and it’s blank, assign "1"
        if len(sub_idx) == 1 and len(to_fill) == 1:
            i = sub_idx[0]
            x.at[i, "mount_id_str"] = "1"
            filled_count += 1
            fills.append({
                "excel_row_1based": i + 2,
                "foundation_root": fr,
                "data_location": x.at[i, "Data location"],
                "date_mount": str(x.at[i, "date_mount"]),
                "old_mount_id": "",
                "new_mount_id": "1",
                "reason": "single_row_group_default_1",
            })
            continue

        # For multi-row groups: deterministic ordering on marker columns
        # Assign mount_id = 1..N in that order, but never overwrite an existing mount_id.
        order_df = x.loc[sub_idx, sort_cols].copy()
        for c in sort_cols:
            order_df[c] = order_df[c].apply(_s)

        order_df = order_df.sort_values(sort_cols, kind="mergesort")
        ordered_idx = order_df.index.tolist()

        # Build the sequence of ids for this group based on position in ordered list
        # If some rows already have mount_id, keep them; fill only blanks with their position number.
        for pos, i in enumerate(ordered_idx, start=1):
            if i in to_fill:
                new_id = str(pos)
                x.at[i, "mount_id_str"] = new_id
                filled_count += 1
                fills.append({
                    "excel_row_1based": i + 2,
                    "foundation_root": fr,
                    "data_location": x.at[i, "Data location"],
                    "date_mount": str(x.at[i, "date_mount"]),
                    "old_mount_id": "",
                    "new_mount_id": new_id,
                    "reason": "sorted_marker_columns_position",
                })

    # write back mount_id as mount_id_str (string-safe)
    x["mount_id"] = x["mount_id_str"]

    # drop helper cols for output xlsx
    drop_cols = ["Data_location_norm","foundation_root","date_mount_dt","mount_id_str"]
    out_x = x.drop(columns=[c for c in drop_cols if c in x.columns])

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as w:
        out_x.to_excel(w, sheet_name=SHEET, index=False)

    pd.DataFrame(fills).to_csv(OUT_MAP, sep="\t", index=False)
    pd.DataFrame([{
        "rows_total": int(len(x)),
        "rows_filled_mount_id": int(filled_count),
        "fill_events_logged": int(len(fills)),
    }]).to_csv(OUT_QC, sep="\t", index=False)

    print(f"[OK] wrote {OUT_XLSX}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_MAP}")

if __name__ == "__main__":
    main()
