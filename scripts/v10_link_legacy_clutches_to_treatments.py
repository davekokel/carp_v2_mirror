#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Dict, Set, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

DEFAULT_IN_ROI = "seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv"


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def norm(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).strip()


def split_codes(val: str | None) -> List[str]:
    if val is None:
        return []
    text_val = str(val)
    if text_val.lower().strip() in ("", "nan", "none", "na"):
        return []
    text_norm = (
        text_val.replace(";", ",")
        .replace("|", ",")
    )
    parts: List[str] = []
    for chunk in text_norm.split(","):
        c = chunk.strip()
        if not c:
            continue
        parts.append(c)
    return parts


def build_construct_lookup(engine: Engine) -> Dict[str, str]:
    sql = text(
        """
        SELECT
          c.id::text      AS construct_id,
          c.construct_code,
          c.base_code,
          a.alias
        FROM public.constructs c
        LEFT JOIN public.construct_aliases a
          ON a.construct_id = c.id
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    lookup: Dict[str, str] = {}
    for _, row in df.iterrows():
        construct_code = norm(row["construct_code"])
        base_code      = norm(row["base_code"])
        alias          = norm(row.get("alias"))

        canon = construct_code or base_code
        if not canon:
            continue

        keys: Set[str] = set()
        for k in (construct_code, base_code, alias):
            k = norm(k)
            if not k:
                continue
            keys.add(k)
            keys.add(k.lower())

        for k in keys:
            lookup[k] = canon

    print(f"[v10_link_legacy_clutches] construct alias keys: {len(lookup)}")
    return lookup


def build_dye_alias_lookup(engine: Engine) -> Dict[str, str]:
    sql = text(
        """
        SELECT dye_base_code, name
        FROM public.dyes
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    alias_to_base: Dict[str, str] = {}
    for _, row in df.iterrows():
        base = norm(row["dye_base_code"])
        name = norm(row.get("name"))
        if not base:
            continue

        candidates: Set[str] = set()

        for raw in (base, name):
            r = norm(raw)
            if not r:
                continue

            candidates.add(r)
            candidates.add(r.lower())

            r_no_space = r.replace(" ", "")
            candidates.add(r_no_space)
            candidates.add(r_no_space.lower())

            if "-" in r:
                r_space = r.replace("-", " ")
                candidates.add(r_space)
                candidates.add(r_space.lower())
                r_space_no = r_space.replace(" ", "")
                candidates.add(r_space_no)
                candidates.add(r_space_no.lower())
            if " " in r:
                r_dash = r.replace(" ", "-")
                candidates.add(r_dash)
                candidates.add(r_dash.lower())
                r_dash_no = r_dash.replace(" ", "")
                candidates.add(r_dash_no)
                candidates.add(r_dash_no.lower())

        for key in candidates:
            alias_to_base[key] = base

    print(f"[v10_link_legacy_clutches] dye alias keys: {len(alias_to_base)}")
    return alias_to_base


def find_plasmid_col(df: pd.DataFrame) -> Optional[str]:
    if "treatment_plasmid_plasmid_base_code_from_enrich" in df.columns:
        return "treatment_plasmid_plasmid_base_code_from_enrich"
    if "treatment_plasmid_plasmid_base_code" in df.columns:
        return "treatment_plasmid_plasmid_base_code"
    return None


def find_rna_col(df: pd.DataFrame) -> Optional[str]:
    if "treatment_rna_rna_base_code_from_enrich" in df.columns:
        return "treatment_rna_rna_base_code_from_enrich"
    if "treatment_rna_rna_base_code" in df.columns:
        return "treatment_rna_rna_base_code"
    return None


def find_extra_dye_col(df: pd.DataFrame) -> Optional[str]:
    for c in df.columns:
        if c.strip().lower() == "additonal dye and chemicals":
            return c
    return None


def find_roi_code_col(df: pd.DataFrame) -> Optional[str]:
    # Our CSV uses bruker_roi_id as the canonical ROI code (e.g. 20250428-plate1-slot1-roi1)
    for c in df.columns:
        if c.strip().lower() == "bruker_roi_id":
            return c
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: link legacy clutches to treatments using ROI CSV + normalized treatments."
    )
    parser.add_argument(
        "--roi-csv",
        default=DEFAULT_IN_ROI,
        help=f"Path to legacy_imaging_annotations_for_db_v9.csv (default: {DEFAULT_IN_ROI})",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL for DB lookups",
    )
    args = parser.parse_args()

    roi_path = Path(args.roi_csv)
    if not roi_path.exists():
        raise SystemExit(f"[v10_link_legacy_clutches] ROI CSV not found: {roi_path}")

    print(f"[v10_link_legacy_clutches] reading ROI CSV: {roi_path}")
    df = pd.read_csv(roi_path)

    plasmid_col   = find_plasmid_col(df)
    rna_col       = find_rna_col(df)
    extra_dye_col = find_extra_dye_col(df)
    roi_code_col  = find_roi_code_col(df)

    if roi_code_col is None:
        raise SystemExit("[v10_link_legacy_clutches] Could not find bruker_roi_id column in ROI CSV.")

    engine           = get_engine(args.db_url)
    construct_lookup = build_construct_lookup(engine)
    dye_aliases      = build_dye_alias_lookup(engine)

    # ── 1) Compute signature per ROI row ─────────────────────────────────────
    records: List[Dict[str, object]] = []

    for _, row in df.iterrows():
        plasmid_raw = row[plasmid_col] if plasmid_col and plasmid_col in df.columns else None
        rna_raw     = row[rna_col]     if rna_col and rna_col in df.columns else None
        extra_raw   = row[extra_dye_col] if extra_dye_col and extra_dye_col in df.columns else None

        plasmid_codes = split_codes(plasmid_raw)
        rna_codes     = split_codes(rna_raw)
        extra_dyes_v9 = split_codes(extra_raw)

        construct_codes: Set[str] = set()
        for bc in plasmid_codes + rna_codes:
            key = norm(bc)
            if not key:
                continue
            canon = construct_lookup.get(key) or construct_lookup.get(key.lower())
            if not canon:
                continue
            construct_codes.add(canon)

        dye_codes_used: Set[str] = set()
        for raw in extra_dyes_v9:
            k = norm(raw)
            if not k:
                continue
            k_norms = {
                k,
                k.lower(),
                k.replace(" ", ""),
                k.replace(" ", "").lower(),
            }
            base = None
            for kk in k_norms:
                if kk in dye_aliases:
                    base = dye_aliases[kk]
                    break
            if base is None:
                continue
            dye_codes_used.add(base)

        if not construct_codes and not dye_codes_used:
            continue

        construct_sig = ",".join(sorted(construct_codes)) if construct_codes else ""
        dye_sig       = ",".join(sorted(dye_codes_used)) if dye_codes_used else ""
        sig           = f"constructs={construct_sig}|dyes={dye_sig}"

        roi_code = norm(row[roi_code_col])

        records.append(
            {
                "roi_code": roi_code,
                "signature": sig,
            }
        )

    if not records:
        print("[v10_link_legacy_clutches] No ROI rows with treatments; nothing to link.")
        return

    df_roi_sig = pd.DataFrame(records).drop_duplicates(subset=["roi_code"]).reset_index(drop=True)
    print(f"[v10_link_legacy_clutches] ROI rows with treatments: {len(df_roi_sig)}")

    # ── 2) signature -> treat_code mapping (must match builder's scheme) ─────
    sig_records: List[Dict[str, object]] = []
    seen_sigs: Set[str] = set()
    for r in records:
        sig = r["signature"]
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)
        sig_records.append({"signature": sig})

    df_sig = pd.DataFrame(sig_records).reset_index(drop=True)
    print(f"[v10_link_legacy_clutches] unique signatures: {len(df_sig)}")

    df_sig["treatment_code"] = [
        f"T-LEGACY-{i+1:03d}" for i in range(len(df_sig))
    ]
    sig_to_treat: Dict[str, str] = dict(zip(df_sig["signature"], df_sig["treatment_code"]))

    # ── 3) Map roi_code -> clutch_id via DB ──────────────────────────────────
    sql_map = text(
        """
        SELECT
          ra.roi_code,
          icm.clutch_id::text AS clutch_id
        FROM public.imaging_roi_annotations ra
        JOIN public.imaging_slots s
          ON s.id = ra.slot_id
        JOIN public.imaging_clutch_memberships icm
          ON icm.slot_id = s.id
        """
    )
    with engine.begin() as cx:
        df_map = pd.read_sql(sql_map, cx)

    df_map["roi_code"] = df_map["roi_code"].astype(str).str.strip()
    print(f"[v10_link_legacy_clutches] DB ROI→clutch rows (by roi_code): {len(df_map)}")

    # ── 4) Combine ROI-level signatures with clutch mapping ──────────────────
    merged = df_roi_sig.merge(df_map, on="roi_code", how="inner")
    merged = merged.dropna(subset=["clutch_id", "signature"]).reset_index(drop=True)
    print(f"[v10_link_legacy_clutches] ROI rows with clutch + signature: {len(merged)}")

    if merged.empty:
        print("[v10_link_legacy_clutches] No ROI rows could be mapped to clutches; nothing to link.")
        return

    merged["treatment_code"] = merged["signature"].map(sig_to_treat)
    merged = merged.dropna(subset=["treatment_code"]).reset_index(drop=True)

    if merged.empty:
        print("[v10_link_legacy_clutches] No ROI signatures matched treatment codes; nothing to link.")
        return

    df_pairs = (
        merged[["clutch_id", "treatment_code"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    print(f"[v10_link_legacy_clutches] unique (clutch_id, treatment_code) pairs: {len(df_pairs)}")

    # ── 5) Resolve treatment_ids ─────────────────────────────────────────────
    sql_treat = text(
        """
        SELECT id::text AS treatment_id, treat_code
        FROM public.treatments
        WHERE treat_code = ANY(:codes)
        """
    )
    codes = df_pairs["treatment_code"].astype(str).tolist()
    with engine.begin() as cx:
        df_treat = pd.read_sql(sql_treat, cx, params={"codes": codes})

    tcode_to_id: Dict[str, str] = dict(zip(df_treat["treat_code"], df_treat["treatment_id"]))
    print(f"[v10_link_legacy_clutches] treatment rows found for linking: {len(tcode_to_id)}")

    df_pairs["treatment_id"] = df_pairs["treatment_code"].map(tcode_to_id)
    df_pairs = df_pairs.dropna(subset=["treatment_id"]).reset_index(drop=True)

    if df_pairs.empty:
        print("[v10_link_legacy_clutches] No treatment_ids could be resolved; nothing to link.")
        return

    # ── 6) Insert into join_clutch_treatments ───────────────────────────────
    insert_sql = text(
        """
        INSERT INTO public.join_clutch_treatments (
          id,
          clutch_id,
          treatment_id,
          applied_at,
          notes,
          created_at
        )
        VALUES (
          gen_random_uuid(),
          :clutch_id,
          :treatment_id,
          now(),
          NULL,
          now()
        )
        ON CONFLICT DO NOTHING
        """
    )

    to_insert: List[Tuple[str, str]] = list(
        { (str(r["clutch_id"]), str(r["treatment_id"])) for _, r in df_pairs.iterrows() }
    )

    inserted = 0
    with engine.begin() as cx:
        for clutch_id, treatment_id in to_insert:
            cx.execute(
                insert_sql,
                {"clutch_id": clutch_id, "treatment_id": treatment_id},
            )
            inserted += 1

    print(f"[v10_link_legacy_clutches] inserted {inserted} join_clutch_treatments row(s)")

if __name__ == "__main__":
    main()
