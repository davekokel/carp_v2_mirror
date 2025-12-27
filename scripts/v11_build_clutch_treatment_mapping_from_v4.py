#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

EMPTY_SIG = "plasmids=|rnas=|dyes="


def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


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


def _pipe_to_sorted_csv(pipe_blob: str) -> str:
    s = _s(pipe_blob)
    if not s:
        return ""
    parts = [p.strip() for p in s.split("|") if p.strip()]
    parts = sorted(dict.fromkeys(parts))
    return ",".join(parts)


def _signature_text(plasmids_blob: object, rnas_blob: object) -> str:
    plas_pipe = _canon_codes_blob(plasmids_blob)
    rnas_pipe = _canon_codes_blob(rnas_blob)
    return f"plasmids={_pipe_to_sorted_csv(plas_pipe)}|rnas={_pipe_to_sorted_csv(rnas_pipe)}|dyes="


def _treat_code_from_signature(sig: str) -> str:
    s = _s(sig)
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"T-EXP-{h}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--ideal-tsv",
        default="seed_kits/legacy_wrangling_v4/working/ideal_imaging_import_sheet_v4.fixed.tsv",
    )
    ap.add_argument(
        "--clutch-col",
        default="legacy_clutch_key",
    )
    ap.add_argument(
        "--out-csv",
        required=True,
    )
    ap.add_argument(
        "--infer-source",
        default="legacy_wrangling_v4_ideal",
    )
    ap.add_argument(
        "--infer-rule",
        default="ideal_sheet:legacy_clutch_key+treatment_*_base_codes",
    )
    ap.add_argument(
        "--infer-batch-id",
        default="legacy_wrangling_v4_ideal",
    )
    args = ap.parse_args()

    ideal_tsv = Path(args.ideal_tsv)
    out_csv = Path(args.out_csv)
    clutch_col = str(args.clutch_col).strip()

    if not ideal_tsv.exists():
        raise SystemExit(f"[STOP] missing ideal TSV: {ideal_tsv}")

    df = pd.read_csv(ideal_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [str(c).strip() for c in df.columns]

    if clutch_col not in df.columns:
        raise SystemExit(f"[STOP] ideal TSV missing --clutch-col '{clutch_col}'")

    need_cols = ["roi_path", "treatment_plasmid_base_codes", "treatment_rna_base_codes"]
    miss = [c for c in need_cols if c not in df.columns]
    if miss:
        raise SystemExit(f"[STOP] ideal TSV missing columns: {miss}")

    df["roi_path"] = df["roi_path"].astype(str).map(_s)
    df = df[df["roi_path"].ne("")].copy()

    df[clutch_col] = df[clutch_col].astype(str).map(_s)
    df = df[df[clutch_col].ne("")].copy()

    df["signature_text"] = df.apply(
        lambda r: _signature_text(r.get("treatment_plasmid_base_codes", ""), r.get("treatment_rna_base_codes", "")),
        axis=1,
    )
    df["signature_text"] = df["signature_text"].astype(str).map(_s)
    df = df[df["signature_text"].ne(EMPTY_SIG)].copy()

    if len(df) == 0:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            columns=["clutch_code", "treat_code", "treat_text", "n_rois", "treatment_infer_source", "treatment_infer_rule", "treatment_infer_batch_id"]
        ).to_csv(out_csv, index=False)
        print(str(out_csv))
        return

    df["treat_text"] = df["signature_text"].astype(str)
    df["treat_code"] = df["treat_text"].map(_treat_code_from_signature)

    per = (
        df.groupby(clutch_col, as_index=False)
        .agg(
            n_rois=("roi_path", "size"),
            n_treat_codes=("treat_code", lambda s: len({x for x in s if _s(x)})),
            treat_code=("treat_code", lambda s: ";".join(sorted({x for x in s if _s(x)}))),
            treat_text=("treat_text", lambda s: ";".join(sorted({x for x in s if _s(x)}))),
        )
    )

    multi = per[per["n_treat_codes"].astype(int) != 1].copy()
    if len(multi):
        print(multi.sort_values(["n_treat_codes", clutch_col], ascending=[False, True]).head(200).to_string(index=False))
        raise SystemExit("[STOP] clutches with !=1 treatment signature; fix in ideal sheet (or upstream rules).")

    out = per[[clutch_col, "treat_code", "treat_text", "n_rois"]].copy()
    out = out.rename(columns={clutch_col: "clutch_code"})
    out["treatment_infer_source"] = str(args.infer_source)
    out["treatment_infer_rule"] = str(args.infer_rule)
    out["treatment_infer_batch_id"] = str(args.infer_batch_id)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(str(out_csv))


if __name__ == "__main__":
    main()
