#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def _norm_base(tok: str) -> str:
    t = _s(tok).lower()
    if not t:
        return ""
    t = re.sub(r"[^a-z0-9\-]+", "", t)
    m = re.match(r"^([a-z]+)-?0*([0-9]+)$", t)
    if m:
        return f"{m.group(1)}-{int(m.group(2))}"
    return t


def _split_basecodes(blob: object) -> List[str]:
    s = _s(blob).lower()
    if not s:
        return []
    toks = [t.strip() for t in re.split(r"[|,;]+", s) if t.strip()]
    out: List[str] = []
    seen = set()
    for t in toks:
        t2 = _norm_base(t)
        if t2 and t2 not in seen:
            seen.add(t2)
            out.append(t2)
    return out


def _extract_basecodes_from_text(blob: object) -> List[str]:
    s = _s(blob).lower()
    if not s:
        return []
    found = re.findall(r"\b([a-z]{2,})-?0*([0-9]{1,4})\b", s)
    out: List[str] = []
    seen = set()
    for a, n in found:
        t = f"{a}-{int(n)}"
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _extract_alleles_from_text(blob: object) -> List[str]:
    s = _s(blob)
    if not s:
        return []
    out: List[str] = []
    for m in re.finditer(r"\b([0-9]{1,4})\b", s):
        out.append(m.group(1))
    return out


def _read_tiff_list(txt: Path) -> pd.DataFrame:
    lines = txt.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows: List[Tuple[str, str]] = []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        rows.append((ln, "1"))
    df = pd.DataFrame(rows, columns=["tiff_path", "n"])
    df["tiff_path"] = df["tiff_path"].map(_s)
    df = df[df["tiff_path"].ne("")].copy()

    def roi_path_from_tiff(p: str) -> str:
        pp = Path(p)
        parent = pp.parent
        return str(parent)

    df["roi_path"] = df["tiff_path"].map(roi_path_from_tiff)
    g = df.groupby("roi_path", as_index=False)["n"].count()
    g.rename(columns={"n": "n_tiffs"}, inplace=True)
    g["n_tiffs"] = g["n_tiffs"].astype(int).astype(str)
    return g[["roi_path", "n_tiffs"]]


def _read_imaging_sheet(xlsx: Path) -> pd.DataFrame:
    df = pd.read_excel(xlsx, dtype=str).fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    def pick(*names: str) -> str:
        for n in names:
            if n in df.columns:
                return n
        return ""

    col_data_loc = pick("Data location", "data_location", "Data Location")
    col_date_mount = pick("date_mount", "Date mounted", "Date mount", "date_mounted", "date_mounting")
    col_targets = pick("Unique Targets", "Unique Targets with blanks", "Unique targets", "unique_targets")
    col_add_plasmids = pick("additional plasmids injected", "Additional plasmids injected", "additional_plasmids_injected")
    col_add_mrnas = pick("additional mRNAs injected", "Additional mRNAs injected", "additional_mrnas_injected")
    col_zf_f = pick("ZF female genotype", "zf_female_genotype", "female_genotype")
    col_zf_m = pick("ZF male genotype", "zf_male_genotype", "male_genotype")

    keep = []
    for c in [col_data_loc, col_date_mount, col_targets, col_add_plasmids, col_add_mrnas, col_zf_f, col_zf_m]:
        if c:
            keep.append(c)

    out = df[keep].copy() if keep else pd.DataFrame({"__empty__": [""] * len(df)})
    out.rename(
        columns={
            col_data_loc: "data_location",
            col_date_mount: "date_mount",
            col_targets: "unique_targets",
            col_add_plasmids: "additional_plasmids_injected",
            col_add_mrnas: "additional_mrnas_injected",
            col_zf_f: "zf_female_genotype",
            col_zf_m: "zf_male_genotype",
        },
        inplace=True,
    )

    for c in ["data_location", "date_mount", "unique_targets", "additional_plasmids_injected", "additional_mrnas_injected", "zf_female_genotype", "zf_male_genotype"]:
        if c not in out.columns:
            out[c] = ""
        out[c] = out[c].astype(str).fillna("").map(_s)

    out = out[out["data_location"].ne("")].copy()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="seed_kits/legacy_wrangling_v5/raw")
    ap.add_argument("--work-dir", default="seed_kits/legacy_wrangling_v5/working")
    ap.add_argument("--imaging-xlsx", default="seed_kits/legacy_wrangling_v5/raw/2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx")
    ap.add_argument("--tiffs-txt", default="seed_kits/legacy_wrangling_v5/raw/foundation_tiff_files_20251223_140835.txt")
    ap.add_argument("--out-csv", default="seed_kits/legacy_wrangling_v5/working/roi_path_to_markers_v5.csv")
    args = ap.parse_args()

    imaging_xlsx = Path(args.imaging_xlsx)
    tiffs_txt = Path(args.tiffs_txt)
    out_csv = Path(args.out_csv)
    work_dir = Path(args.work_dir)

    if not imaging_xlsx.exists():
        raise SystemExit(f"[STOP] missing imaging sheet: {imaging_xlsx}")
    if not tiffs_txt.exists():
        raise SystemExit(f"[STOP] missing tiff list: {tiffs_txt}")

    roi = _read_tiff_list(tiffs_txt)
    roi["roi_path"] = roi["roi_path"].map(_s)

    sheet = _read_imaging_sheet(imaging_xlsx)

    sheet["data_location"] = sheet["data_location"].map(_s)

    def match_row_for_roi_path(roi_path: str) -> int:
        rp = _s(roi_path)
        if not rp:
            return -1
        hits = sheet.index[sheet["data_location"].map(lambda dl: rp.startswith(_s(dl)) and _s(dl) != "")].tolist()
        if not hits:
            return -1
        best = max(hits, key=lambda i: len(sheet.loc[i, "data_location"]))
        return int(best)

    match_idx = [match_row_for_roi_path(rp) for rp in roi["roi_path"].tolist()]
    roi["sheet_row_idx"] = match_idx

    out = roi[["roi_path", "n_tiffs", "sheet_row_idx"]].copy()

    for c in ["genotype_base_codes", "genotype_allele_codes", "treatment_rna_base_codes", "treatment_plasmid_base_codes"]:
        out[c] = ""

    missing_sheet = out["sheet_row_idx"].astype(int).eq(-1)
    if (~missing_sheet).any():
        idxs = out.loc[~missing_sheet, "sheet_row_idx"].astype(int).tolist()
        sub = sheet.loc[idxs].reset_index(drop=True)
        out_sub = out.loc[~missing_sheet].reset_index(drop=True)

        geno_base: List[str] = []
        geno_alle: List[str] = []
        tr_rna: List[str] = []
        tr_plasmid: List[str] = []

        for i in range(len(out_sub)):
            r = sub.iloc[i]
            bases = []
            alleles = []

            bases += _extract_basecodes_from_text(r.get("zf_female_genotype", ""))
            bases += _extract_basecodes_from_text(r.get("zf_male_genotype", ""))
            if bases:
                bases = [_norm_base(b) for b in bases if _norm_base(b)]
                bases = sorted(list(dict.fromkeys(bases)))

            alleles += _extract_alleles_from_text(r.get("zf_female_genotype", ""))
            alleles += _extract_alleles_from_text(r.get("zf_male_genotype", ""))
            if alleles:
                alleles = [a for a in alleles if a]
                alleles = sorted(list(dict.fromkeys(alleles)))

            geno_base.append("|".join(bases))
            geno_alle.append("|".join(alleles))

            rna = []
            rna += _split_basecodes(r.get("additional_mrnas_injected", ""))
            rna += _split_basecodes(r.get("unique_targets", ""))
            rna = [_norm_base(x) for x in rna if _norm_base(x)]
            rna = sorted(list(dict.fromkeys(rna)))
            tr_rna.append("|".join(rna))

            plasm = []
            plasm += _split_basecodes(r.get("additional_plasmids_injected", ""))
            plasm += _split_basecodes(r.get("unique_targets", ""))
            plasm = [_norm_base(x) for x in plasm if _norm_base(x)]
            plasm = sorted(list(dict.fromkeys(plasm)))
            tr_plasmid.append("|".join(plasm))

        out.loc[~missing_sheet, "genotype_base_codes"] = geno_base
        out.loc[~missing_sheet, "genotype_allele_codes"] = geno_alle
        out.loc[~missing_sheet, "treatment_rna_base_codes"] = tr_rna
        out.loc[~missing_sheet, "treatment_plasmid_base_codes"] = tr_plasmid

    out.drop(columns=["sheet_row_idx"], inplace=True)

    marker_cols = ["genotype_base_codes", "genotype_allele_codes", "treatment_rna_base_codes", "treatment_plasmid_base_codes"]
    for c in marker_cols:
        out[c] = out[c].astype(str).fillna("").map(_s)

    qc = out_csv.with_suffix(".qc.tsv")
    qc_fill = out_csv.with_suffix(".qc_fill_rates.tsv")
    qc_missing = out_csv.with_suffix(".qc_missing_samples.tsv")

    n = len(out)
    miss_mask = (out[marker_cols].astype(str).apply(lambda r: all(_s(v) == "" for v in r.values), axis=1))
    miss_samples = out.loc[miss_mask, ["roi_path", "n_tiffs"]].head(50).copy()
    qc_missing.parent.mkdir(parents=True, exist_ok=True)
    miss_samples.to_csv(qc_missing, sep="\t", index=False)

    rows = []
    for c in ["roi_path", "n_tiffs", *marker_cols]:
        nn = int((out[c].astype(str).str.strip() != "").sum())
        rows.append((c, nn, n, round(100.0 * nn / n, 3)))
    pd.DataFrame(rows, columns=["column", "n_nonempty", "n_rows", "pct_nonempty"]).to_csv(qc_fill, sep="\t", index=False)

    qc_rows = [
        ("imaging_xlsx", str(imaging_xlsx)),
        ("tiffs_txt", str(tiffs_txt)),
        ("out_csv", str(out_csv)),
        ("rows", str(n)),
        ("rows_all_markers_blank", str(int(miss_mask.sum()))),
        ("qc_fill_rates", str(qc_fill)),
        ("qc_missing_samples", str(qc_missing)),
    ]
    pd.DataFrame(qc_rows, columns=["key", "value"]).to_csv(qc, sep="\t", index=False)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)

    print(f"[OK] wrote {out_csv} rows={len(out)}")
    print(f"[QC] {qc}")
    print(f"[QC] {qc_fill}")
    print(f"[QC] {qc_missing}")


if __name__ == "__main__":
    main()
