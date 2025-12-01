#!/usr/bin/env python3
from __future__ import annotations
import argparse, os
from pathlib import Path
from typing import Dict, Set, List
import pandas as pd
from sqlalchemy import create_engine, text

DEFAULT_IN_ROI = "seed_kits/organizely_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv"
DEFAULT_OUT    = "seed_kits/2025-11-15-121231-autoload/treatments_v10.csv"

def get_engine(db_url: str | None):
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)

def norm(x):
    if x is None:
        return ""
    return str(x).strip()

def split_codes(val):
    if val is None:
        return []
    s = str(val)
    if s.strip() == "" or s.strip().lower() in ("nan", "na", "none"):
        return []
    parts = []
    tmp = s.replace(";", ",")
    for chunk in tmp.split(","):
        c = chunk.strip()
        if c:
            parts.append(c)
    return parts

def find_plasmid_col(df: pd.DataFrame):
    for c in df.columns:
        if c == "treatment_plasmid_plasmid_base_code_from_enrich":
            return c
        if c == "treatment_plasmid_plasmid_base_code":
            return c
    return None

def find_rna_col(df: pd.DataFrame):
    for c in df.columns:
        if c == "treatment_rna_rna_base_code_from_enrich":
            return c
        if c == "treatment_rna_rna_base_code":
            return c
    return None

def find_extra_dye_col(df: pd.DataFrame):
    for c in df.columns:
        if norm(c) == "additonal dye and chemicals":
            return c
    return None

def build_construct_lookup(cx) -> Dict[str,str]:
    df = pd.read_sql(
        text(
            """
            SELECT
              c.construct_code,
              c.base_code,
              a.alias
            FROM public.constructs c
            LEFT JOIN public.construct_aliases a
              ON a.construct_id = c.id
            """
        ),
        cx,
    )
    lut: Dict[str,str] = {}
    for _, r in df.iterrows():
        canon = norm(r["base_code"] or r["construct_code"])
        if not canon:
            continue
        keys: Set[str] = set()
        for k in [r["construct_code"], r["base_code"], r["alias"]]:
            k = norm(k)
            if not k:
                continue
            keys.add(k)
            keys.add(k.lower())
            ks = k.replace(" ", "")
            kd = k.replace("-", "")
            if ks:
                keys.add(ks)
            if kd:
                keys.add(kd)
        for k in keys:
            lut[k] = canon
    print(f"[v10_build_legacy_treatments] construct alias keys: {len(lut)}")
    return lut

def build_dye_lookup(cx) -> Dict[str,str]:
    df = pd.read_sql(
        text("SELECT dye_base_code, name FROM public.dyes"),
        cx,
    )
    lut: Dict[str,str] = {}
    for _, r in df.iterrows():
        base = norm(r["dye_base_code"])
        if not base:
            continue
        name = norm(r.get("name"))
        for raw in [base, name]:
            v = norm(raw)
            if not v:
                continue
            for k in [v, v.lower(), v.replace(" ", ""), v.replace(" ", "").lower(),
                      v.replace("-", ""), v.replace("-", "").lower()]:
                if k:
                    lut[k] = base
    print(f"[v10_build_legacy_treatments] dye alias keys: {len(lut)}")
    return lut

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--roi-csv", default=DEFAULT_IN_ROI)
    p.add_argument("--out-csv", default=DEFAULT_OUT)
    p.add_argument("--db-url")
    args = p.parse_args()

    roi_path = Path(args.roi_csv)
    if not roi_path.exists():
        raise SystemExit(f"[v10_build_legacy_treatments] ROI CSV not found: {roi_path}")
    print(f"[v10_build_legacy_treatments] reading ROI CSV: {roi_path}")
    df = pd.read_csv(roi_path)

    plasmid_col = find_plasmid_col(df)
    rna_col = find_rna_col(df)
    extra_dye_col = find_extra_dye_col(df)

    if plasmid_col is None and rna_col is None and extra_dye_col is None:
        raise SystemExit("[v10_build_legacy_treatments] no plasmid/RNA/extra-dye columns; cannot build treatments")

    engine = get_engine(args.db_url)
    records: List[dict] = []
    unknown_constructs: Set[str] = set()
    unknown_dyes: Set[str] = set()

    with engine.begin() as cx:
        c_lut = build_construct_lookup(cx)
        d_lut = build_dye_lookup(cx)

        for _, row in df.iterrows():
            plasmid_raw = row[plasmid_col] if plasmid_col and plasmid_col in df.columns else None
            rna_raw = row[rna_col] if rna_col and rna_col in df.columns else None
            extra_raw = row[extra_dye_col] if extra_dye_col and extra_dye_col in df.columns else None

            plasmid_codes = split_codes(plasmid_raw)
            rna_codes = split_codes(rna_raw)
            extra_dyes = split_codes(extra_raw)

            constructs: Set[str] = set()
            for bc in plasmid_codes + rna_codes:
                k0 = norm(bc)
                if not k0:
                    continue
                ks = {k0, k0.lower(), k0.replace(" ", ""), k0.replace("-", ""), k0.replace(" ", "").lower()}
                canon = None
                for kk in ks:
                    if kk in c_lut:
                        canon = c_lut[kk]
                        break
                if not canon:
                    unknown_constructs.add(k0)
                    continue
                constructs.add(canon)

            dyes: Set[str] = set()
            for raw in extra_dyes:
                k0 = norm(raw)
                if not k0:
                    continue
                ks = {k0, k0.lower(), k0.replace(" ", ""), k0.replace("-", ""), k0.replace(" ", "").lower()}
                base = None
                for kk in ks:
                    if kk in d_lut:
                        base = d_lut[kk]
                        break
                if base is None:
                    unknown_dyes.add(k0)
                    continue
                dyes.add(base)

            if not constructs and not dyes:
                continue

            sig_c = ",".join(sorted(constructs)) if constructs else ""
            sig_d = ",".join(sorted(dyes)) if dyes else ""
            sig = f"constructs={sig_c}|dyes={sig_d}"
            records.append(
                {"signature": sig, "construct_codes": sorted(constructs), "dye_codes": sorted(dyes)}
            )

        if unknown_constructs or unknown_dyes:
            parts: List[str] = []
            if unknown_constructs:
                parts.append("constructs=" + ",".join(sorted(unknown_constructs)))
            if unknown_dyes:
                parts.append("dyes=" + ",".join(sorted(unknown_dyes)))
            raise SystemExit(
                "[v10_build_legacy_treatments] unknown codes in ROI sheet or constructs/dyes: " + "; ".join(parts)
            )

        if not records:
            raise SystemExit("[v10_build_legacy_treatments] no rows with treatment constructs/dyes; fix ROI/constructs/dyes first")

        sig_df = (
            pd.DataFrame(records)
            .drop_duplicates(subset=["signature"])
            .reset_index(drop=True)
        )
        print(f"[v10_build_legacy_treatments] unique treatment signatures: {len(sig_df)}")

        out_rows: List[dict] = []
        for i, r in sig_df.iterrows():
            constructs = r["construct_codes"]
            dyes = r["dye_codes"]
            tcode = f"T-LEGACY-{i+1:03d}"
            tname = f"Legacy v9 mix {i+1}"
            kind = "injection"
            mix = "M1"
            for c in constructs:
                out_rows.append(
                    {
                        "treatment_code": tcode,
                        "treatment_name": tname,
                        "kind_code": kind,
                        "mix_code": mix,
                        "ingredient_type": "construct",
                        "ingredient_code": c,
                        "concentration": None,
                    }
                )
            for d in dyes:
                out_rows.append(
                    {
                        "treatment_code": tcode,
                        "treatment_name": tname,
                        "kind_code": kind,
                        "mix_code": mix,
                        "ingredient_type": "dye",
                        "ingredient_code": d,
                        "concentration": None,
                    }
                )

        out = Path(args.out_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(out_rows).to_csv(out, index=False)
        print(f"[v10_build_legacy_treatments] wrote {len(out_rows)} row(s) to {out}")

