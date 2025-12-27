from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

TOKEN_SPLIT = re.compile(r"[|,;\s]+")
def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def _canon_one(tok: str) -> str:
    s = _s(tok)
    if not s:
        return ""
    m = re.search(r"(?i)\b(mgco|pdqm|hc|pswin|swin)-?0*([0-9]+)\b", s)
    if not m:
        return ""
    pref = m.group(1).lower()
    num = int(m.group(2))
    if pref == "swin":
        pref = "pswin"
    return f"{pref}-{num}"

def _canon_pipe_list(blob: object) -> List[str]:
    s = _s(blob)
    if not s:
        return []
    code_re = re.compile(r"(?i)\b(mgco|pdqm|hc|pswin|swin)-?0*([0-9]+)\b")
    out: List[str] = []
    seen: Set[str] = set()
    for mm in code_re.finditer(s):
        pref = mm.group(1).lower()
        num = int(mm.group(2))
        if pref == "swin":
            pref = "pswin"
        tok = f"{pref}-{num}"
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return sorted(out)

def _sig_from(plas: List[str], rnas: List[str]) -> str:
    p_csv = ",".join(sorted(dict.fromkeys([p for p in plas if p])))
    r_csv = ",".join(sorted(dict.fromkeys([r for r in rnas if r])))
    return f"plasmids={p_csv}|rnas={r_csv}|dyes="


def _treat_code_from_signature(sig: str) -> str:
    s = _s(sig)
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"T-EXP-{h}"


def _load_overrides(path: Path) -> Dict[str, str]:
    if not path.exists():
        raise SystemExit(f"[STOP] missing overrides TSV: {path}")
    out: Dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        need = {"base_code", "kind"}
        if not r.fieldnames or any(c not in r.fieldnames for c in need):
            raise SystemExit(f"[STOP] overrides TSV must have columns: base_code, kind ({path})")
        for row in r:
            b = _canon_one(row.get("base_code", ""))
            k = _s(row.get("kind", "")).lower()
            if not b:
                continue
            if k not in ("plasmid", "rna"):
                raise SystemExit(f"[STOP] invalid kind '{k}' for base_code '{b}' in {path} (must be plasmid|rna)")
            out[b] = k
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_with_treatments_v4.tsv")
    ap.add_argument("--overrides-tsv", default="seed_kits/legacy_wrangling_v4/working/treatment_base_kind_overrides_v4.tsv")
    ap.add_argument("--out-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_with_treatments_v4.patched.tsv")
    ap.add_argument("--qc-overlap", default="seed_kits/legacy_wrangling_v4/working/ideal_with_treatments_v4.patched.qc_overlap.tsv")
    ap.add_argument("--qc-unresolved", default="seed_kits/legacy_wrangling_v4/working/ideal_with_treatments_v4.patched.qc_unresolved.tsv")
    args = ap.parse_args()

    inp = Path(args.in_tsv)
    ovp = Path(args.overrides_tsv)
    outp = Path(args.out_tsv)
    qcp_overlap = Path(args.qc_overlap)
    qcp_unresolved = Path(args.qc_unresolved)

    if not inp.exists():
        raise SystemExit(f"[STOP] missing input TSV: {inp}")

    overrides = _load_overrides(ovp)

    rows_out: List[dict] = []
    overlap_rows: List[Tuple[int, str, str, str]] = []
    unresolved_rows: List[Tuple[int, str, str]] = []

    with inp.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        if not r.fieldnames:
            raise SystemExit(f"[STOP] empty TSV: {inp}")
        fieldnames = list(r.fieldnames)

        need_cols = [
            "roi_path",
            "treatment_plasmid_base_codes",
            "treatment_rna_base_codes",
            "signature_text",
            "treat_code",
            "locked_treatment",
            "source_of_treatment",
        ]
        for c in need_cols:
            if c not in fieldnames:
                raise SystemExit(f"[STOP] input TSV missing column '{c}': {inp}")

        for i, row in enumerate(r, start=2):
            roi_path = _s(row.get("roi_path", ""))

            p_raw = row.get("treatment_plasmid_base_codes", "")
            r_raw = row.get("treatment_rna_base_codes", "")

            p_list = _canon_pipe_list(p_raw)
            r_list = _canon_pipe_list(r_raw)

            pb: Set[str] = set(p_list)
            rb: Set[str] = set(r_list)
            both = sorted(pb & rb)

            if both:
                decided = []
                unresolved = []
                for b in both:
                    k = overrides.get(b)
                    if not k:
                        unresolved.append(b)
                        continue
                    if k == "plasmid":
                        rb.discard(b)
                        decided.append(f"{b}->plasmid")
                    else:
                        pb.discard(b)
                        decided.append(f"{b}->rna")

                if decided:
                    overlap_rows.append((i, roi_path, ",".join(both), ",".join(decided)))

                if unresolved:
                    unresolved_rows.append((i, roi_path, ",".join(unresolved)))

            p2 = sorted(pb)
            r2 = sorted(rb)

            sig = _sig_from(p2, r2)
            tcode = _treat_code_from_signature(sig)

            outrow = dict(row)
            outrow["treatment_plasmid_base_codes"] = "|".join(p2)
            outrow["treatment_rna_base_codes"] = "|".join(r2)
            outrow["signature_text"] = sig
            outrow["treat_code"] = tcode
            rows_out.append(outrow)

    if unresolved_rows:
        qcp_unresolved.parent.mkdir(parents=True, exist_ok=True)
        with qcp_unresolved.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["line", "roi_path", "unresolved_bases"])
            w.writerows(unresolved_rows)
        raise SystemExit(f"[STOP] {len(unresolved_rows)} row(s) have base code(s) in BOTH plasmid and rna with no override. See {qcp_unresolved}")

    if overlap_rows:
        qcp_overlap.parent.mkdir(parents=True, exist_ok=True)
        with qcp_overlap.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["line", "roi_path", "bases_in_both", "decisions"])
            w.writerows(overlap_rows)

    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows_out[0].keys() if rows_out else [], delimiter="\t")
        w.writeheader()
        for row in rows_out:
            w.writerow(row)

    print("WROTE", outp, "rows", len(rows_out))
    if overlap_rows:
        print("WROTE_QC", qcp_overlap, "rows", len(overlap_rows))
    else:
        print("[OK] no overlaps found after canonicalization")


if __name__ == "__main__":
    main()
