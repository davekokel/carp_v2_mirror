from __future__ import annotations

from pathlib import Path
import pandas as pd
import re

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_STEP1 = WORKING / "roi_path_to_session_step1_v5.csv"
IN_ROI_SLUGS = WORKING / "roi_path_slugs_v5.csv"
IN_XLSX = WORKING / "master_imaging_list_mountid_filled_v5.xlsx"
SHEET = "Master Imaging list"

OUT = WORKING / "roi_path_to_session_step14_v5.csv"
OUT_QC = QC / "roi_path_to_session_step14_v5.qc.tsv"
OUT_AMBIG = QC / "roi_path_to_session_step14_v5.qc_ambiguous.tsv"
OUT_MISS = QC / "roi_path_to_session_step14_v5.qc_unfilled.tsv"

RE_DATE8 = re.compile(r"^(\d{8})")
RE_FISH_PREFIX = re.compile(r"^fish\d+_", re.IGNORECASE)

def _s(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()

def norm_path(s: str) -> str:
    return str(s).strip().replace("\\", "/")

def exp_date_from_folder(folder: str) -> str:
    m = RE_DATE8.match(str(folder))
    return m.group(1) if m else ""

def build_session_id(fr: str, date_mount, mount_id) -> str:
    dm = pd.to_datetime(date_mount, errors="coerce")
    mid = _s(mount_id)
    if fr and pd.notna(dm) and mid:
        return f"{fr}__{dm.strftime('%Y-%m-%d')}__{mid}"
    return ""

def roi_clue_tokens(roi_path: str) -> list[str]:
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

def score_blob(blob: str, toks: list[str]) -> int:
    s = 0
    for t in toks:
        if t and t in blob:
            s += 1
    return s

def main() -> None:
    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    step1 = pd.read_csv(IN_STEP1)
    if not {"roi_path", "session_id"}.issubset(set(step1.columns)):
        raise SystemExit("[STOP] step1 missing roi_path/session_id")

    slugs = pd.read_csv(IN_ROI_SLUGS)[["roi_path","foundation_root","experiment_folder"]].copy()
    slugs["experiment_date"] = slugs["experiment_folder"].map(exp_date_from_folder)

    df = slugs.merge(step1, on="roi_path", how="left")
    df["session_id"] = df["session_id"].fillna("").astype(str)

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)
    for c in ["Data location","date_mount","mount_id"]:
        if c not in x.columns:
            raise SystemExit(f"[STOP] missing column in filled sheet: {c}")

    blob_cols = [
        "ZF female genotype","ZF male genotype",
        "additional plasmids injected","additional mRNAs injected","additonal dye and chemicals",
        "Unique Targets","Unique Targets with blanks",
        "Imaged Locations","free_text_label","comments",
    ]
    for c in blob_cols:
        if c not in x.columns:
            x[c] = ""

    x = x.copy()
    x["dl"] = x["Data location"].astype(str).map(norm_path)
    x["fr"] = x["dl"].str.extract(r"(Aang_Foundation|Korra_Foundation)")[0].fillna("")
    x["date_mount_dt"] = pd.to_datetime(x["date_mount"], errors="coerce")
    x["session_id"] = [build_session_id(fr, dm, mid) for fr, dm, mid in zip(x["fr"], x["date_mount"], x["mount_id"])]
    x = x[x["session_id"].astype(str).str.len() > 0].copy()
    x["blob"] = x[blob_cols].astype(str).agg(" | ".join, axis=1).str.lower()

    ambig = []
    miss = []

    out_session = []
    out_source = []
    out_score = []
    out_ncand = []

    for _, r in df.iterrows():
        cur = _s(r["session_id"])
        if cur:
            out_session.append(cur)
            out_source.append("step1")
            out_score.append("")
            out_ncand.append("")
            continue

        roi_path = r["roi_path"]
        fr = r["foundation_root"]
        ef = r["experiment_folder"]
        exp_date = _s(r["experiment_date"])
        toks = roi_clue_tokens(roi_path)

        cand = x[x["fr"] == fr].copy()

        if exp_date:
            exp_dt = pd.to_datetime(exp_date, format="%Y%m%d", errors="coerce")
            if pd.notna(exp_dt):
                lo = exp_dt.normalize() - pd.Timedelta(days=1)
                hi = exp_dt.normalize() + pd.Timedelta(days=1)
                cand = cand[(cand["date_mount_dt"] >= lo) & (cand["date_mount_dt"] <= hi)].copy()

        if len(cand) == 0:
            out_session.append("")
            out_source.append("unfilled")
            out_score.append("")
            out_ncand.append(0)
            miss.append({"roi_path": roi_path, "foundation_root": fr, "experiment_folder": ef, "experiment_date": exp_date, "reason": "no_candidates_in_window"})
            continue

        if not toks:
            out_session.append("")
            out_source.append("unfilled")
            out_score.append("")
            out_ncand.append(int(len(cand)))
            ambig.append({"roi_path": roi_path, "foundation_root": fr, "experiment_folder": ef, "experiment_date": exp_date, "reason": "no_roi_tokens", "n_candidates": int(len(cand))})
            continue

        cand["score"] = cand["blob"].apply(lambda b: score_blob(b, toks))
        best = cand.sort_values(["score"], ascending=False)
        top_score = int(best.iloc[0]["score"])
        top = best[best["score"] == top_score]

        if top_score < 2:
            out_session.append("")
            out_source.append("unfilled")
            out_score.append(top_score)
            out_ncand.append(int(len(cand)))
            ambig.append({"roi_path": roi_path, "foundation_root": fr, "experiment_folder": ef, "experiment_date": exp_date, "reason": "score_below_threshold", "top_score": top_score, "n_candidates": int(len(cand)), "tokens": ";".join(toks)})
            continue

        if len(top) == 1:
            out_session.append(str(top.iloc[0]["session_id"]))
            out_source.append("step4")
            out_score.append(top_score)
            out_ncand.append(int(len(cand)))
            continue

        out_session.append("")
        out_source.append("unfilled")
        out_score.append(top_score)
        out_ncand.append(int(len(cand)))
        ambig.append({
            "roi_path": roi_path,
            "foundation_root": fr,
            "experiment_folder": ef,
            "experiment_date": exp_date,
            "reason": "tie_on_score",
            "top_score": top_score,
            "n_top": int(len(top)),
            "session_ids_top": " || ".join(sorted(set(top["session_id"].astype(str).tolist()))[:10]),
            "tokens": ";".join(toks),
        })

    df_out = pd.DataFrame({
        "roi_path": df["roi_path"],
        "session_id": out_session,
        "source": out_source,
        "score": out_score,
        "n_candidates": out_ncand,
    })
    df_out.to_csv(OUT, index=False)

    qc = {
        "roi_paths_total": int(len(df_out)),
        "session_id_present": int((df_out["session_id"].astype(str).str.len() > 0).sum()),
        "session_id_missing": int((df_out["session_id"].astype(str).str.len() == 0).sum()),
        "filled_by_step4": int((df_out["source"] == "step4").sum()),
        "still_missing": int((df_out["source"] == "unfilled").sum()),
        "ambiguous_logged": int(len(ambig)),
        "unfilled_logged": int(len(miss)),
    }
    pd.DataFrame([qc]).to_csv(OUT_QC, sep="\t", index=False)
    pd.DataFrame(ambig).to_csv(OUT_AMBIG, sep="\t", index=False)
    pd.DataFrame(miss).to_csv(OUT_MISS, sep="\t", index=False)

    print(f"[OK] wrote {OUT} rows={len(df_out)}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_AMBIG}")
    print(f"[QC] wrote {OUT_MISS}")

if __name__ == "__main__":
    main()
