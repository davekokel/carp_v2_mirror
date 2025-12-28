from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_ROI_SLUGS = WORKING / "roi_path_slugs_v5.csv"
IN_LINK = WORKING / "experiment_linkage_v5.tsv"
IN_CAND = WORKING / "experiment_linkage_v5_candidates.tsv"
IN_XLSX = RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
SHEET = "Master Imaging list"

OUT = WORKING / "roi_path_to_session_v5.csv"
OUT_QC = QC / "roi_path_to_session_v5.qc.tsv"
OUT_CLASS4 = QC / "roi_path_to_session_v5.class4_missing.tsv"
OUT_CLASS3_AMBIG = QC / "roi_path_to_session_v5.class3_ambiguous.tsv"


def _s(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def choose_candidate(cands: pd.DataFrame, exp_date_yyyymmdd: str) -> tuple[pd.Series, str]:
    """
    Deterministic chooser for class3:
      1) unique mode of (mom,dad,plasmids,rna,dye) signature
      2) closest in time to exp_date using date_mount else date_imaged
      3) if still tied, pick first but mark ambiguous_tie
    """
    if len(cands) == 0:
        raise ValueError("empty candidates")

    def sig_row(r) -> tuple[str, str, str, str, str]:
        return (
            _s(r.get("mom_parent_cell")),
            _s(r.get("dad_parent_cell")),
            _s(r.get("inj_plasmids_cell")),
            _s(r.get("inj_rna_cell")),
            _s(r.get("inj_dye_cell")),
        )

    c = cands.copy()
    c["sig"] = c.apply(sig_row, axis=1)
    vc = c["sig"].value_counts()
    top_n = int(vc.iloc[0])
    top_sigs = vc[vc == top_n].index.tolist()
    if len(top_sigs) == 1:
        sig = top_sigs[0]
        return c[c["sig"] == sig].iloc[0], "mode"

    exp_dt = pd.to_datetime(exp_date_yyyymmdd, format="%Y%m%d", errors="coerce")
    if pd.notna(exp_dt):
        def delta_days(r):
            dm = pd.to_datetime(r.get("date_mount"), errors="coerce")
            di = pd.to_datetime(r.get("date_imaged"), errors="coerce")
            if pd.notna(dm):
                return abs((dm.normalize() - exp_dt.normalize()).days)
            if pd.notna(di):
                return abs((di.normalize() - exp_dt.normalize()).days)
            return 10**9
        c["delta"] = c.apply(delta_days, axis=1)
        min_d = int(c["delta"].min())
        best = c[c["delta"] == min_d]
        if len(best) == 1:
            return best.iloc[0], "closest_time"
        return best.iloc[0], "ambiguous_tie"

    return c.iloc[0], "ambiguous_no_date"


def main() -> None:
    for p in (IN_ROI_SLUGS, IN_LINK, IN_CAND, IN_XLSX):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    roi = pd.read_csv(IN_ROI_SLUGS)[["roi_path", "foundation_root", "experiment_folder"]].copy()
    link = pd.read_csv(IN_LINK, sep="\t")
    cand = pd.read_csv(IN_CAND, sep="\t")
    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)

    for c in ["date_mount", "mount_id"]:
        if c not in x.columns:
            raise SystemExit(f"[STOP] Master Imaging list missing column: {c}")

    # Build experiment -> chosen excel_idx0, with provenance
    exp_choice: dict[tuple[str, str], dict[str, str | int]] = {}
    class4_rows = []
    class3_ambig = []

    for _, r in link.iterrows():
        fr = r["foundation_root"]
        ef = r["experiment_folder"]
        cls = r["link_class"]
        rule = _s(r.get("rule"))
        exp_date = _s(r.get("experiment_date"))
        key = (fr, ef)

        if cls in ("class1", "class2"):
            row_1 = _s(r.get("chosen_excel_row_1based"))
            if not row_1:
                continue
            try:
                idx0 = int(float(row_1)) - 2
            except Exception:
                continue
            exp_choice[key] = {
                "excel_idx0": idx0,
                "link_class": cls,
                "chosen_method": cls,
                "link_rule": rule,
                "excel_row_1based": row_1,
            }
            continue

        if cls == "class3":
            cdf = cand[(cand["foundation_root"] == fr) & (cand["experiment_folder"] == ef)].copy()
            if len(cdf) == 0:
                class3_ambig.append({"foundation_root": fr, "experiment_folder": ef, "reason": "no_candidate_rows"})
                continue
            row, method = choose_candidate(cdf, exp_date)
            row_1 = _s(row.get("excel_row_1based"))
            try:
                idx0 = int(float(row_1)) - 2
            except Exception:
                class3_ambig.append({"foundation_root": fr, "experiment_folder": ef, "reason": "bad_excel_row_number", "chosen_method": method, "excel_row_1based": row_1})
                continue

            exp_choice[key] = {
                "excel_idx0": idx0,
                "link_class": cls,
                "chosen_method": method,
                "link_rule": rule,
                "excel_row_1based": row_1,
            }
            if method.startswith("ambiguous"):
                class3_ambig.append({"foundation_root": fr, "experiment_folder": ef, "reason": method, "excel_row_1based": row_1, "n_candidates": int(len(cdf))})
            continue

        if cls == "class4":
            class4_rows.append({"foundation_root": fr, "experiment_folder": ef, "reason": "no_candidates"})
            continue

    pd.DataFrame(class4_rows).to_csv(OUT_CLASS4, sep="\t", index=False)
    pd.DataFrame(class3_ambig).to_csv(OUT_CLASS3_AMBIG, sep="\t", index=False)

    # ROI-level output
    out_rows = []
    for _, rr in roi.iterrows():
        roi_path = rr["roi_path"]
        fr = rr["foundation_root"]
        ef = rr["experiment_folder"]
        key = (fr, ef)

        date_mount_id = ""
        excel_row_1based = ""
        link_class = ""
        chosen_method = ""
        link_rule = ""

        ch = exp_choice.get(key)
        if ch is not None:
            idx0 = int(ch["excel_idx0"])
            excel_row_1based = str(ch.get("excel_row_1based", ""))
            link_class = str(ch.get("link_class", ""))
            chosen_method = str(ch.get("chosen_method", ""))
            link_rule = str(ch.get("link_rule", ""))

            if 0 <= idx0 < len(x):
                xr = x.iloc[idx0]
                dm = pd.to_datetime(xr.get("date_mount"), errors="coerce")
                mid = _s(xr.get("mount_id"))
                if pd.notna(dm) and mid:
                    date_mount_id = dm.strftime("%Y-%m-%d") + "__" + mid

        out_rows.append({
            "roi_path": roi_path,
            "date_mount_id": date_mount_id,
            "excel_row_1based": excel_row_1based,
            "link_class": link_class,
            "chosen_method": chosen_method,
            "link_rule": link_rule,
        })

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT, index=False)

    qc = {
        "roi_paths_total": int(len(out_df)),
        "roi_with_date_mount_id": int((out_df["date_mount_id"].astype(str).str.len() > 0).sum()),
        "roi_missing_date_mount_id": int((out_df["date_mount_id"].astype(str).str.len() == 0).sum()),
        "experiments_linked": int(len(exp_choice)),
        "experiments_class4": int(len(class4_rows)),
        "class3_ambig_logged": int(len(class3_ambig)),
    }
    pd.DataFrame([qc]).to_csv(OUT_QC, sep="\t", index=False)

    print(f"[OK] wrote {OUT} rows={len(out_df)}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_CLASS4}")
    print(f"[QC] wrote {OUT_CLASS3_AMBIG}")

if __name__ == "__main__":
    main()
