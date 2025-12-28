from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

SPLIT_RX = re.compile(r"[;,]\s*|\s+")

PDQM_RX = re.compile(r"^(?:p)?pdqm[-_ ]?0*(\d+)$", re.I)
MGCO_RX = re.compile(r"^(?:p)?mgco[-_ ]?0*(\d+)$", re.I)
HC_RX   = re.compile(r"^(?:p)?hc[-_ ]?0*(\d+)$", re.I)
PSWIN_RX = re.compile(r"^(?:p)?pswin[-_ ]?0*(\d+)$", re.I)

def split_blob(v: Optional[str]) -> List[str]:
    if v is None:
        return []
    s = str(v).strip()
    if not s or s.lower() in {"none", "nan"}:
        return []
    return [p.strip() for p in SPLIT_RX.split(s) if p and p.strip()]

def canon_base_code(tok: str) -> Tuple[str, str]:
    t = tok.strip()
    if not t:
        return ("", "empty")

    t_lc = t.lower().replace("_", "-").replace(" ", "-")

    m = PDQM_RX.match(t_lc)
    if m:
        return (f"pdqm-{int(m.group(1))}", "ok")

    m = MGCO_RX.match(t_lc)
    if m:
        return (f"mgco-{int(m.group(1))}", "ok")

    m = HC_RX.match(t_lc)
    if m:
        return (f"hc-{int(m.group(1))}", "ok")

    m = PSWIN_RX.match(t_lc)
    if m:
        return (f"pswin-{int(m.group(1))}", "ok")

    return (t_lc, "unknown")

def canon_blob(blob: Optional[str]) -> Tuple[str, List[Tuple[str, str, str]]]:
    toks = split_blob(blob)
    out: List[str] = []
    qc: List[Tuple[str, str, str]] = []
    seen = set()

    for tok in toks:
        canon, status = canon_base_code(tok)
        if canon and canon not in seen:
            seen.add(canon)
            out.append(canon)
        qc.append((tok, canon, status))

    return ("; ".join(out), qc)

def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python v5_normalize_roi_path_map_for_upload.py /path/to/roi_path_to_session_markers_v5_manual_*.csv [out_dir]")

    src = Path(sys.argv[1]).expanduser().resolve()
    out_dir = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) >= 3 else src.parent

    wide_out = out_dir / "roi_path_to_session_markers_v5_normalized.csv"
    geno_out = out_dir / "roi_genotype_constructs_v5_normalized.csv"
    trt_out  = out_dir / "roi_treatment_constructs_v5_normalized.csv"
    qc_out   = out_dir / "roi_path_map_v5_normalization_qc.csv"

    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, str]] = []
    geno_rows: List[Dict[str, str]] = []
    trt_rows: List[Dict[str, str]] = []
    qc_rows: List[Dict[str, str]] = []

    with src.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        header = list(r.fieldnames or [])
        need = {
            "roi_path",
            "date_mount_id",
            "genotype_base_codes",
            "genotype_allele_codes",
            "treatment_rna_base_codes",
            "treatment_plasmid_base_codes",
        }
        missing = [c for c in sorted(need) if c not in header]
        if missing:
            raise SystemExit(f"[STOP] missing columns in {src}: {missing}")

        for row in r:
            roi_path = (row.get("roi_path") or "").strip()
            if not roi_path:
                continue

            gb_norm, gb_qc = canon_blob(row.get("genotype_base_codes"))
            tr_norm, tr_qc = canon_blob(row.get("treatment_rna_base_codes"))
            tp_norm, tp_qc = canon_blob(row.get("treatment_plasmid_base_codes"))

            out_row = dict(row)
            out_row["genotype_base_codes_raw"] = row.get("genotype_base_codes") or ""
            out_row["treatment_rna_base_codes_raw"] = row.get("treatment_rna_base_codes") or ""
            out_row["treatment_plasmid_base_codes_raw"] = row.get("treatment_plasmid_base_codes") or ""
            out_row["genotype_base_codes"] = gb_norm
            out_row["treatment_rna_base_codes"] = tr_norm
            out_row["treatment_plasmid_base_codes"] = tp_norm
            rows.append(out_row)

            alleles = split_blob(row.get("genotype_allele_codes"))
            bases = split_blob(gb_norm)
            if bases:
                if alleles and len(alleles) == len(bases):
                    for b, a in zip(bases, alleles):
                        if b:
                            geno_rows.append({"roi_path": roi_path, "construct_base_code": b, "allele_code": (a or "").strip()})
                else:
                    for b in bases:
                        if b:
                            geno_rows.append({"roi_path": roi_path, "construct_base_code": b, "allele_code": ""})

            for b in split_blob(tr_norm):
                if b:
                    trt_rows.append({"roi_path": roi_path, "kind": "rna", "construct_base_code": b})
            for b in split_blob(tp_norm):
                if b:
                    trt_rows.append({"roi_path": roi_path, "kind": "plasmid", "construct_base_code": b})

            for (raw, canon, status) in gb_qc:
                qc_rows.append({"roi_path": roi_path, "field": "genotype_base_codes", "raw_token": raw, "canon_token": canon, "status": status})
            for (raw, canon, status) in tr_qc:
                qc_rows.append({"roi_path": roi_path, "field": "treatment_rna_base_codes", "raw_token": raw, "canon_token": canon, "status": status})
            for (raw, canon, status) in tp_qc:
                qc_rows.append({"roi_path": roi_path, "field": "treatment_plasmid_base_codes", "raw_token": raw, "canon_token": canon, "status": status})

    def write_csv(path: Path, fieldnames: List[str], recs: List[Dict[str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for rr in recs:
                w.writerow({k: (rr.get(k) if rr.get(k) is not None else "") for k in fieldnames})

    wide_fields = list(rows[0].keys()) if rows else [
        "roi_path","date_mount_id",
        "genotype_base_codes","genotype_allele_codes",
        "treatment_rna_base_codes","treatment_plasmid_base_codes",
        "genotype_base_codes_raw","treatment_rna_base_codes_raw","treatment_plasmid_base_codes_raw"
    ]
    write_csv(wide_out, wide_fields, rows)
    write_csv(geno_out, ["roi_path","construct_base_code","allele_code"], geno_rows)
    write_csv(trt_out, ["roi_path","kind","construct_base_code"], trt_rows)
    write_csv(qc_out, ["roi_path","field","raw_token","canon_token","status"], qc_rows)

    n_unknown = sum(1 for r in qc_rows if r["status"] != "ok")
    print(f"[OK] input:  {src}")
    print(f"[OK] wide:   {wide_out} rows={len(rows)}")
    print(f"[OK] geno:   {geno_out} rows={len(geno_rows)}")
    print(f"[OK] trt:    {trt_out} rows={len(trt_rows)}")
    print(f"[OK] qc:     {qc_out} rows={len(qc_rows)} unknown={n_unknown}")

if __name__ == "__main__":
    main()
