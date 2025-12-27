from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import List, Tuple

OK_BASE = re.compile(r"^(mgco|pdqm|hc|pswin)-\d+$", re.I)
FIND_CODE = re.compile(r"(mgco|pdqm|hc|pswin|swin)\s*[-_ ]?\s*0*([0-9]+)", re.I)

def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s

def _canon_base_list(blob: object) -> List[str]:
    s = _s(blob)
    if not s:
        return []
    out: List[str] = []
    seen = set()
    for m in FIND_CODE.finditer(s):
        pref = m.group(1).lower()
        num = int(m.group(2))
        if pref == "swin":
            pref = "pswin"
        tok = f"{pref}-{num}"
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return sorted(out)

def _canon_allele_list(blob: object) -> List[str]:
    s = _s(blob)
    if not s:
        return []
    parts = re.split(r"[|,;\s]+", s)
    out: List[str] = []
    for p in parts:
        p = _s(p)
        if not p:
            continue
        # common legacy nicknames like 'is01' -> '1'
        m = re.match(r"(?i)^is0*([0-9]+)$", p.strip())
        if m:
            out.append(str(int(m.group(1))))
            continue
        # otherwise: extract first numeric run (e.g., 'allele 315' -> 315)
        m2 = re.search(r"([0-9]+)", p)
        if not m2:
            continue
        out.append(str(int(m2.group(1))))
    return out

def _base_sort_key(b: str) -> Tuple[int, str, int]:
    b = b.lower()
    m = re.match(r"^([a-z]+)-([0-9]+)$", b)
    if not m:
        return (9, b, 0)
    pref = m.group(1)
    num = int(m.group(2))
    pref_rank = {"pdqm": 1, "mgco": 2, "hc": 3, "pswin": 4}.get(pref, 8)
    return (pref_rank, pref, num)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_with_genotypes_v4.tsv")
    ap.add_argument("--out-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_with_genotypes_v4.patched.tsv")
    ap.add_argument("--qc-bad", default="seed_kits/legacy_wrangling_v4/working/ideal_with_genotypes_v4.patched.qc_bad.tsv")
    ap.add_argument("--qc-mismatch", default="seed_kits/legacy_wrangling_v4/working/ideal_with_genotypes_v4.patched.qc_len_mismatch.tsv")
    args = ap.parse_args()

    inp = Path(args.in_tsv)
    outp = Path(args.out_tsv)
    qc_bad = Path(args.qc_bad)
    qc_mis = Path(args.qc_mismatch)

    if not inp.exists():
        raise SystemExit(f"[STOP] missing input TSV: {inp}")

    rows_out: List[dict] = []
    bad_rows: List[Tuple[int, str, str, str]] = []
    mis_rows: List[Tuple[int, str, str, str]] = []

    with inp.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        if not r.fieldnames:
            raise SystemExit(f"[STOP] empty TSV: {inp}")
        fieldnames = list(r.fieldnames)
        need = {"roi_path", "genotype_base_codes", "genotype_allele_codes"}
        miss = [c for c in need if c not in fieldnames]
        if miss:
            raise SystemExit(f"[STOP] input TSV missing columns: {miss}")

        for i, row in enumerate(r, start=2):
            rp = _s(row.get("roi_path", ""))
            b0 = row.get("genotype_base_codes", "")
            a0 = row.get("genotype_allele_codes", "")

            b_list = _canon_base_list(b0)
            a_list = _canon_allele_list(a0)

            if b_list and any(not OK_BASE.match(x) for x in b_list):
                bad_rows.append((i, rp, str(b0), "|".join(b_list)))

            if len(b_list) == 1 and len(a_list) == 2:
                b_list = [b_list[0], b_list[0]]

            if len(b_list) != len(a_list) and (b_list or a_list):
                mis_rows.append((i, rp, "|".join(b_list), "|".join(a_list)))

            if len(b_list) == len(a_list) and len(b_list) > 0:
                pairs = list(zip(b_list, a_list))
                pairs.sort(key=lambda p: (_base_sort_key(p[0]), str(p[1])))
                b_list = [p[0] for p in pairs]
                a_list = [p[1] for p in pairs]

            outrow = dict(row)
            outrow["genotype_base_codes"] = "|".join(b_list)
            outrow["genotype_allele_codes"] = "|".join(a_list)
            rows_out.append(outrow)

    if mis_rows:
        qc_mis.parent.mkdir(parents=True, exist_ok=True)
        with qc_mis.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["line", "roi_path", "genotype_base_codes_norm", "genotype_allele_codes_norm"])
            w.writerows(mis_rows)
        raise SystemExit(f"[STOP] {len(mis_rows)} row(s) have base/allele length mismatch after normalization. See {qc_mis}")

    if bad_rows:
        qc_bad.parent.mkdir(parents=True, exist_ok=True)
        with qc_bad.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["line", "roi_path", "bases_raw", "bases_norm"])
            w.writerows(bad_rows)

    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=(rows_out[0].keys() if rows_out else []), delimiter="\t")
        w.writeheader()
        for row in rows_out:
            w.writerow(row)

    print("WROTE", outp, "rows", len(rows_out))
    if bad_rows:
        print("WROTE_QC", qc_bad, "rows", len(bad_rows))
    else:
        print("[OK] genotype basecodes canonical")

if __name__ == "__main__":
    main()
