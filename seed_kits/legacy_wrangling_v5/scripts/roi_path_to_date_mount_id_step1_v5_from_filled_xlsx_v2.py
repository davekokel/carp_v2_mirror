from __future__ import annotations

from pathlib import Path
import pandas as pd
import re

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_ROI_SLUGS = WORKING / "roi_path_slugs_v5.csv"
IN_XLSX = WORKING / "master_imaging_list_mountid_filled_v5.xlsx"
SHEET = "Master Imaging list"

OUT = WORKING / "roi_path_to_date_mount_id_step1_v5.csv"
OUT_QC = QC / "roi_path_to_date_mount_id_step1_v5.qc.tsv"
OUT_AMBIG = QC / "roi_path_to_date_mount_id_step1_v5.qc_ambiguous.tsv"
OUT_MISS = QC / "roi_path_to_date_mount_id_step1_v5.qc_missing.tsv"

RE_DATE8 = re.compile(r"^(\d{8})")
RE_FISH_PREFIX = re.compile(r"^fish\d+_", re.IGNORECASE)

def _s(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()

def norm_path(s: str) -> str:
    return str(s).strip().replace("\\", "/")

def build_date_mount_id(date_mount, mount_id) -> str:
    dm = pd.to_datetime(date_mount, errors="coerce")
    mid = _s(mount_id)
    if pd.notna(dm) and mid:
        return dm.strftime("%Y-%m-%d") + "__" + mid
    return ""

def roi_clue_tokens(roi_path: str) -> list[str]:
    """
    Use the folder immediately under experiment_folder as the discriminating clue.
    Example:
      Aang_Foundation/20250808_mem_organelle/fish1_24hpf_mem-mchilada_lyso-mSG/roi1
      -> fish1_24hpf_mem-mchilada_lyso-mSG
    Tokenize lightly; keep meaningful bits (mchilada, lyso, msg, lamp1, mito, etc).
    """
    parts = [p for p in str(roi_path).strip("/").split("/") if p]
    if len(parts) < 3:
        return []
    clue = parts[2].lower()
    clue = RE_FISH_PREFIX.sub("", clue)
    clue = re.sub(r"\b\d+hpf\b", "", clue)
    toks = [t for t in re.split(r"[_\-]+", clue) if t]
    stop = {"fish","roi","hpf","24","48","72","96","120"}
    toks = [t for t in toks if t not in stop]
    return toks

def score_row(blob: str, toks: list[str]) -> int:
    s = 0
    for t in toks:
        if t and t in blob:
            s += 1
    return s

def main() -> None:
    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    roi = pd.read_csv(IN_ROI_SLUGS)[["roi_path","foundation_root","experiment_folder"]].copy()

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)
    for c in ["Data location","date_mount","mount_id"]:
        if c not in x.columns:
            raise SystemExit(f"[STOP] missing column in filled sheet: {c}")

    # build candidate search fields
    cols = [
        "ZF female genotype","ZF male genotype",
        "additional plasmids injected","additional mRNAs injected","additonal dye and chemicals",
        "Unique Targets","Unique Targets with blanks",
        "Imaged Locations","free_text_label","comments",
    ]
    for c in cols:
        if c not in x.columns:
            x[c] = ""

    x = x.copy()
    x["dl"] = x["Data location"].astype(str).map(norm_path)
    x["fr"] = x["dl"].str.extract(r"(Aang_Foundation|Korra_Foundation)")[0].fillna("")
    x["date_mount_id"] = [build_date_mount_id(a,b) for a,b in zip(x["date_mount"], x["mount_id"])]
    x["blob"] = x[cols].astype(str).agg(" | ".join, axis=1).str.lower()

    out_rows = []
    ambig = []
    miss = []

    for _, r in roi.iterrows():
        roi_path = r["roi_path"]
        fr = r["foundation_root"]
        ef = r["experiment_folder"]

        cand = x[(x["fr"]==fr) & (x["dl"].str.contains(ef, na=False))].copy()
        cand = cand[cand["date_mount_id"].astype(str).str.len() > 0].copy()

        if len(cand) == 0:
            out_rows.append({"roi_path": roi_path, "date_mount_id": ""})
            miss.append({"roi_path": roi_path, "foundation_root": fr, "experiment_folder": ef, "reason": "no_candidates_with_date_mount_id"})
            continue

        dmids = sorted(set(cand["date_mount_id"].astype(str).tolist()))
        if len(dmids) == 1:
            out_rows.append({"roi_path": roi_path, "date_mount_id": dmids[0]})
            continue

        toks = roi_clue_tokens(roi_path)
        if not toks:
            out_rows.append({"roi_path": roi_path, "date_mount_id": ""})
            ambig.append({"roi_path": roi_path, "foundation_root": fr, "experiment_folder": ef, "reason": "multi_dmids_no_tokens", "dmids": " || ".join(dmids)})
            continue

        cand["score"] = cand["blob"].apply(lambda b: score_row(b, toks))
        best = cand.sort_values(["score"], ascending=False)
        top_score = int(best.iloc[0]["score"])
        top = best[best["score"] == top_score]

        if top_score == 0:
            out_rows.append({"roi_path": roi_path, "date_mount_id": ""})
            ambig.append({"roi_path": roi_path, "foundation_root": fr, "experiment_folder": ef, "reason": "no_token_hits", "dmids": " || ".join(dmids), "tokens": ";".join(toks)})
            continue

        if len(top) == 1:
            out_rows.append({"roi_path": roi_path, "date_mount_id": str(top.iloc[0]["date_mount_id"])})
            continue

        # still tied
        out_rows.append({"roi_path": roi_path, "date_mount_id": ""})
        ambig.append({
            "roi_path": roi_path,
            "foundation_root": fr,
            "experiment_folder": ef,
            "reason": "tie_on_score",
            "top_score": top_score,
            "dmids": " || ".join(sorted(set(top["date_mount_id"].astype(str).tolist()))),
            "tokens": ";".join(toks),
        })

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT, index=False)

    qc = {
        "roi_paths_total": int(len(out_df)),
        "roi_with_date_mount_id": int((out_df["date_mount_id"].astype(str).str.len()>0).sum()),
        "roi_missing_date_mount_id": int((out_df["date_mount_id"].astype(str).str.len()==0).sum()),
        "ambiguous_logged": int(len(ambig)),
        "missing_logged": int(len(miss)),
    }
    pd.DataFrame([qc]).to_csv(OUT_QC, sep="\t", index=False)
    pd.DataFrame(ambig).to_csv(OUT_AMBIG, sep="\t", index=False)
    pd.DataFrame(miss).to_csv(OUT_MISS, sep="\t", index=False)

    print(f"[OK] wrote {OUT} rows={len(out_df)}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_AMBIG}")
    print(f"[QC] wrote {OUT_MISS}")

if __name__ == "__main__":
    main()
