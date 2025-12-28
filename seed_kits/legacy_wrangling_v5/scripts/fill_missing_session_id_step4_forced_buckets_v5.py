from __future__ import annotations

from pathlib import Path
import pandas as pd
import re

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_STEP14 = WORKING / "roi_path_to_session_step14_v5.csv"   # current step1+step4
IN_ROI_SLUGS = WORKING / "roi_path_slugs_v5.csv"
IN_XLSX = WORKING / "master_imaging_list_mountid_filled_v5.xlsx"
SHEET = "Master Imaging list"

OUT = WORKING / "roi_path_to_session_step14_forced_v5.csv"
OUT_QC = QC / "roi_path_to_session_step14_forced_v5.qc.tsv"
OUT_TIES = QC / "roi_path_to_session_step14_forced_v5.qc_ties.tsv"
OUT_NO_CAND = QC / "roi_path_to_session_step14_forced_v5.qc_no_candidates.tsv"

RE_DATE8 = re.compile(r"^(\d{8})")
RE_FISH_PREFIX = re.compile(r"^fish\d+_", re.IGNORECASE)

BUCKET_RE = re.compile(r"(mem[-_]?mito|mem[-_]?histone|skittl)", re.IGNORECASE)

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

    base = pd.read_csv(IN_STEP14)
    if not {"roi_path","session_id","source"}.issubset(set(base.columns)):
        raise SystemExit("[STOP] step14 file missing required columns roi_path/session_id/source")

    slugs = pd.read_csv(IN_ROI_SLUGS)[["roi_path","foundation_root","experiment_folder"]].copy()
    slugs["experiment_date"] = slugs["experiment_folder"].map(exp_date_from_folder)
    slugs["experiment_slug"] = slugs["experiment_folder"].astype(str).str.replace(r"^(\d{8})[_-]?", "", regex=True)

    df = slugs.merge(base[["roi_path","session_id","source"]], on="roi_path", how="left")
    df["session_id"] = df["session_id"].fillna("").astype(str)
    df["source"] = df["source"].fillna("").astype(str)

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

    ties = []
    no_cand = []

    out_session = []
    out_source = []

    for _, r in df.iterrows():
        cur = _s(r["session_id"])
        slug = _s(r["experiment_slug"])
        if cur:
            out_session.append(cur)
            out_source.append(r["source"] if r["source"] else "step1_or_step4")
            continue

        # only force-fill for target buckets
        if not BUCKET_RE.search(slug):
            out_session.append("")
            out_source.append("unfilled")
            continue

        roi_path = r["roi_path"]
        fr = r["foundation_root"]
        ef = r["experiment_folder"]
        exp_date = _s(r["experiment_date"])
        toks = roi_clue_tokens(roi_path)

        cand = x[x["fr"] == fr].copy()

        # keep a narrow date window if we can; otherwise allow all dates
        if exp_date:
            exp_dt = pd.to_datetime(exp_date, format="%Y%m%d", errors="coerce")
            if pd.notna(exp_dt):
                lo = exp_dt.normalize() - pd.Timedelta(days=2)
                hi = exp_dt.normalize() + pd.Timedelta(days=2)
                cand = cand[(cand["date_mount_dt"] >= lo) & (cand["date_mount_dt"] <= hi)].copy()

        if len(cand) == 0:
            out_session.append("")
            out_source.append("unfilled_bucket_no_candidates")
            no_cand.append({"roi_path": roi_path, "foundation_root": fr, "experiment_folder": ef, "experiment_slug": slug, "experiment_date": exp_date})
            continue

        # score candidates; if no tokens, score=0 for all
        if toks:
            cand["score"] = cand["blob"].apply(lambda b: score_blob(b, toks))
        else:
            cand["score"] = 0

        # choose highest score; if tie, choose deterministically by earliest date_mount then session_id lexicographically
        best_score = int(cand["score"].max())
        best = cand[cand["score"] == best_score].copy()

        if len(best) > 1:
            best = best.sort_values(["date_mount_dt","session_id"], ascending=[True, True])
            ties.append({
                "roi_path": roi_path,
                "foundation_root": fr,
                "experiment_folder": ef,
                "experiment_slug": slug,
                "experiment_date": exp_date,
                "best_score": best_score,
                "n_tied": int(len(best)),
                "chosen_session_id": str(best.iloc[0]["session_id"]),
                "tied_session_ids": " || ".join(best["session_id"].astype(str).tolist()[:10]),
                "tokens": ";".join(toks),
            })

        chosen = str(best.iloc[0]["session_id"])
        out_session.append(chosen)
        out_source.append("step4_forced_bucket")

    out = pd.DataFrame({
        "roi_path": df["roi_path"],
        "session_id": out_session,
        "source": out_source,
    })
    out.to_csv(OUT, index=False)

    pd.DataFrame(ties).to_csv(OUT_TIES, sep="\t", index=False)
    pd.DataFrame(no_cand).to_csv(OUT_NO_CAND, sep="\t", index=False)

    qc = {
        "roi_paths_total": int(len(out)),
        "session_id_present": int((out["session_id"].astype(str).str.len() > 0).sum()),
        "session_id_missing": int((out["session_id"].astype(str).str.len() == 0).sum()),
        "filled_by_step4_forced_bucket": int((out["source"] == "step4_forced_bucket").sum()),
        "ties_logged": int(len(ties)),
        "no_candidates_logged": int(len(no_cand)),
    }
    pd.DataFrame([qc]).to_csv(OUT_QC, sep="\t", index=False)

    print(f"[OK] wrote {OUT} rows={len(out)}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_TIES}")
    print(f"[QC] wrote {OUT_NO_CAND}")

if __name__ == "__main__":
    main()
