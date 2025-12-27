from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import pandas as pd

EMPTY_SIG = "plasmids=|rnas=|dyes="


def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def _split_tokens(blob: object) -> list[str]:
    s = _s(blob).lower()
    if not s:
        return []
    toks = [t.strip() for t in re.split(r"[|,;]+", s) if t.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for t in toks:
        t = re.sub(r"[^a-z0-9\-]+", "", t)
        m = re.match(r"^([a-z]+)-?0*([0-9]+)$", t)
        if m:
            t = f"{m.group(1)}-{int(m.group(2))}"
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _split_alleles(blob: object) -> list[str]:
    s = _s(blob)
    if not s:
        return []
    parts = [p.strip() for p in s.replace(",", "|").replace(";", "|").split("|") if p.strip()]
    out: list[str] = []
    for p in parts:
        try:
            f = float(p)
            out.append(str(int(f)) if f.is_integer() else str(p).strip())
        except Exception:
            out.append(str(p).strip())
    return out


def _base_sort_key(base: str) -> tuple[int, str, int]:
    b = _s(base).lower()
    m = re.match(r"^([a-z]+)-([0-9]+)$", b)
    if m:
        return (0, m.group(1), int(m.group(2)))
    return (1, b, 0)


def _canon_genotype_pair(base_blob: object, alle_blob: object) -> tuple[str, str]:
    b = _split_tokens(base_blob)
    a = _split_alleles(alle_blob)

    if not b and not a:
        return ("", "")
    if not b and a:
        return ("", "|".join(a))
    if b and not a:
        return ("|".join(b), "")

    if len(b) == 1 and len(a) == 2:
        b = [b[0], b[0]]

    if len(b) != len(a):
        return ("|".join(b), "|".join(a))

    pairs = list(zip(b, a))
    pairs.sort(key=lambda p: (_base_sort_key(p[0]), p[1]))
    b2 = [p[0] for p in pairs]
    a2 = [p[1] for p in pairs]
    return ("|".join(b2), "|".join(a2))


def _treat_code_from_signature(sig: str) -> str:
    s = _s(sig)
    if not s or s == EMPTY_SIG:
        return ""
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"T-EXP-{h}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roi-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_roi_universe_v4.tsv")
    ap.add_argument("--geno-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_with_genotypes_v4.normalized.tsv")
    ap.add_argument("--treat-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_with_treatments_v4.patched.tsv")
    ap.add_argument("--out", default="seed_kits/legacy_wrangling_v4/working/ideal_imaging_import_sheet_v4.fixed.tsv")
    args = ap.parse_args()

    roi_tsv = Path(args.roi_tsv)
    geno_tsv = Path(args.geno_tsv)
    treat_tsv = Path(args.treat_tsv)
    out = Path(args.out)

    for p in [roi_tsv, geno_tsv, treat_tsv]:
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    roi = pd.read_csv(roi_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    roi.columns = [str(c).strip() for c in roi.columns]
    if "roi_path" not in roi.columns:
        raise SystemExit("[STOP] roi-tsv missing roi_path")
    roi["roi_path"] = roi["roi_path"].map(_s)

    g = pd.read_csv(geno_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    g.columns = [str(c).strip() for c in g.columns]
    if "roi_path" not in g.columns:
        raise SystemExit("[STOP] geno-tsv missing roi_path")
    g["roi_path"] = g["roi_path"].map(_s)

    t = pd.read_csv(treat_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    t.columns = [str(c).strip() for c in t.columns]
    if "roi_path" not in t.columns:
        raise SystemExit("[STOP] treat-tsv missing roi_path")
    t["roi_path"] = t["roi_path"].map(_s)

    CARRY_TREAT_COLS = [
        "foundation_guess",
        "date_mount",
        "mount_id",
        "legacy_clutch_key",
        "treatment_plasmid_base_codes",
        "treatment_rna_base_codes",
        "signature_text",
        "treat_code",
        "locked_treatment",
        "source_of_treatment",
    ]
    tcols = [c for c in CARRY_TREAT_COLS if c in t.columns]
    t_small = t[["roi_path", *tcols]].copy()

    roi_set = set(roi["roi_path"].tolist())
    g_set = set(g["roi_path"].tolist())
    t_set = set(t["roi_path"].tolist())

    if roi_set != g_set:
        extra = sorted(list(g_set - roi_set))[:10]
        missing = sorted(list(roi_set - g_set))[:10]
        raise SystemExit(
            f"[STOP] geno roi_path set mismatch. extra_in_geno={len(g_set-roi_set)} missing_in_geno={len(roi_set-g_set)} sample_extra={extra} sample_missing={missing}"
        )
        if roi_set != t_set:
            extra = sorted(list(t_set - roi_set))[:10]
            missing = sorted(list(roi_set - t_set))[:10]
            raise SystemExit(
                f"[STOP] treat roi_path set mismatch. extra_in_treat={len(t_set-roi_set)} missing_in_treat={len(roi_set-t_set)} sample_extra={extra} sample_missing={missing}"
            )

    df = roi.merge(g, on="roi_path", how="left").merge(t_small, on="roi_path", how="left", validate="m:1")

    gb = df.get("genotype_base_codes", "").map(_s)
    ga = df.get("genotype_allele_codes", "").map(_s)
    canon = [ _canon_genotype_pair(b, a) for b, a in zip(gb, ga) ]
    df["genotype_base_codes"] = [x[0] for x in canon]
    df["genotype_allele_codes"] = [x[1] for x in canon]

    bad_rows = []
    for roi_path, b, a in zip(df["roi_path"].tolist(), df["genotype_base_codes"].tolist(), df["genotype_allele_codes"].tolist()):
        bl = [x for x in _s(b).split("|") if x.strip()] if _s(b) else []
        al = [x for x in _s(a).split("|") if x.strip()] if _s(a) else []
        if not bl and not al:
            continue
        if len(bl) != len(al):
            bad_rows.append((roi_path, _s(b), _s(a), len(bl), len(al)))
    if bad_rows:
        qc = Path("seed_kits/legacy_wrangling_v4/working/qc/qc_len_mismatch_after_canon_07d.tsv")
        qc.parent.mkdir(parents=True, exist_ok=True)
        qc.write_text(
            "roi_path\tgenotype_base_codes\tgenotype_allele_codes\tlen_base\tlen_alle\n"
            + "\n".join(f"{rp}\t{b}\t{a}\t{lb}\t{la}" for rp, b, a, lb, la in bad_rows),
            encoding="utf-8",
        )
        raise SystemExit(f"[STOP] genotype len(base)!=len(alle) after canon in 07d: {len(bad_rows)} row(s). See {qc}")

    df["treatment_plasmid_base_codes"] = df.get("treatment_plasmid_base_codes", "").map(_split_tokens).map(lambda xs: "|".join(xs))
    df["treatment_rna_base_codes"] = df.get("treatment_rna_base_codes", "").map(_split_tokens).map(lambda xs: "|".join(xs))

    df["signature_text"] = df.get("signature_text", "").map(_s)
    df.loc[df["signature_text"].eq(""), "signature_text"] = df.apply(
        lambda r: (
            f"plasmids={','.join(sorted([x for x in _s(r.get('treatment_plasmid_base_codes')).split('|') if x]))}"
            f"|rnas={','.join(sorted([x for x in _s(r.get('treatment_rna_base_codes')).split('|') if x]))}"
            f"|dyes="
        ),
        axis=1,
    )
    df["signature_text"] = df["signature_text"].map(_s)
    df.loc[df["signature_text"].eq("plasmids=|rnas=|dyes="), "signature_text"] = EMPTY_SIG

    df["treat_code"] = df.get("treat_code", "").map(_s)
    df.loc[df["treat_code"].eq(""), "treat_code"] = df["signature_text"].map(_treat_code_from_signature)

    if "include_in_db" not in df.columns:
        df["include_in_db"] = "true"
    df["include_in_db"] = df["include_in_db"].map(_s)
    if "dataset_slug" in df.columns:
        df.loc[df["dataset_slug"].map(_s).str.lower().eq("analysis_test"), "include_in_db"] = "false"

    # ENSURE_LEGACY_CLUTCH_COLS: carry clutch identity columns through the final output
    for _c in ["foundation_guess", "date_mount", "mount_id", "legacy_clutch_key"]:
        if _c not in df.columns and _c in t.columns:
            df = df.merge(t[["roi_path", _c]].copy(), on="roi_path", how="left", validate="m:1")

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, sep="\t", index=False)
    print(str(out))
    print("[QC] rows", len(df))


if __name__ == "__main__":
    main()
