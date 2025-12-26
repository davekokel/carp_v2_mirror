from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import pandas as pd


def _s(x: object) -> str:
    return "" if x is None else str(x).strip()


def _blank(x: object) -> bool:
    return _s(x) == ""


def _canon_codes_blob(blob: object) -> str:
    s = _s(blob).lower()
    if not s:
        return ""
    toks = [t.strip() for t in re.split(r"[|,;]+", s) if t.strip()]
    norm = []
    for t in toks:
        t = re.sub(r"[^a-z0-9\-]+", "", t)
        m = re.match(r"^([a-z]+)-?0*([0-9]+)$", t)
        if m:
            t = f"{m.group(1)}-{int(m.group(2))}"
        if t:
            norm.append(t)
    out = []
    seen = set()
    for t in norm:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return "|".join(out)


def _signature_text(plasmids_blob: object, rnas_blob: object) -> str:
    plas = _canon_codes_blob(plasmids_blob)
    rnas = _canon_codes_blob(rnas_blob)

    def pipe_to_csv(x: str) -> str:
        if not x:
            return ""
        parts = [p.strip() for p in x.split("|") if p.strip()]
        parts = sorted(dict.fromkeys(parts))
        return ",".join(parts)

    return f"plasmids={pipe_to_csv(plas)}|rnas={pipe_to_csv(rnas)}|dyes="


def _treat_code_from_signature(sig: str) -> str:
    s = _s(sig)
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"T-EXP-{h}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in",
        dest="inp",
        default="seed_kits/legacy_wrangling_v4/working/ideal_imaging_import_sheet_v4.tsv",
    )
    ap.add_argument(
        "--out",
        default="seed_kits/legacy_wrangling_v4/working/ideal_imaging_import_sheet_v4.fixed.tsv",
    )
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)

    if not inp.exists():
        raise SystemExit(f"[STOP] missing input TSV: {inp}")

    df = pd.read_csv(inp, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [str(c).strip() for c in df.columns]

    for c in [
        "dataset_slug",
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_plasmid_base_codes",
        "treatment_rna_base_codes",
        "source_of_genotype",
        "locked_genotype",
        "source_of_treatment",
        "locked_treatment",
        "signature_text",
        "treat_code",
    ]:
        if c not in df.columns:
            df[c] = ""

    slug = df["dataset_slug"].astype(str).str.strip().str.lower()

    is_mem_histone = slug.str.contains(
        r"(?:^|[_\-])mem[-_]?histone(?:$|[_\-])", regex=True, na=False
    ) | slug.str.contains(r"mem[-_]?histone", regex=True, na=False)

    need_geno = (
        is_mem_histone
        & df["genotype_base_codes"].map(_blank)
        & df["genotype_allele_codes"].map(_blank)
    )
    if int(need_geno.sum()):
        df.loc[need_geno, "genotype_base_codes"] = "pdqm-5|pdqm-133"
        df.loc[need_geno, "genotype_allele_codes"] = "302|324"
        df.loc[need_geno, "source_of_genotype"] = "rule_mem_histone"
        df.loc[need_geno, "locked_genotype"] = "true"

    df["genotype_base_codes"] = df["genotype_base_codes"].map(_canon_codes_blob)
    df["treatment_plasmid_base_codes"] = df["treatment_plasmid_base_codes"].map(_canon_codes_blob)
    df["treatment_rna_base_codes"] = df["treatment_rna_base_codes"].map(_canon_codes_blob)

    df["signature_text"] = df.apply(
        lambda r: _signature_text(
            r.get("treatment_plasmid_base_codes", ""),
            r.get("treatment_rna_base_codes", ""),
        ),
        axis=1,
    )
    df["treat_code"] = df["signature_text"].map(_treat_code_from_signature)

    df["source_of_treatment"] = df["signature_text"].map(
        lambda x: "provided" if _s(x) and _s(x) != "plasmids=|rnas=|dyes=" else ""
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, sep="\t", index=False)
    print(str(out))


if __name__ == "__main__":
    main()