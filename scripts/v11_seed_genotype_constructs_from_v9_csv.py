from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

import pandas as pd
import re
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


ROI_CSV = "seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv"
CLUTCHES_CSV = "seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9.csv"


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def split_slug(slug: str | None) -> List[str]:
    if not slug:
        return []
    s = str(slug).strip()
    if not s or s.lower() == "nan":
        return []
    parts: List[str] = []
    # examples: "pDQM082", "pDQM005,pDQM133"
    for chunk in s.split(","):
        sub = chunk.strip()
        if not sub:
            continue
        # pDQMNNN -> PDQM-NNN
        m = re.fullmatch(r"[pP]DQM(\d{3})", sub)
        if m:
            parts.append(f"PDQM-{m.group(1)}")
            continue
        # If we ever see MGCO style slugs, add logic here.
        # For now, we only handle PDQM.
    return parts


def main() -> None:
    roi_path = Path(ROI_CSV)
    clutch_path = Path(CLUTCHES_CSV)
    if not roi_path.exists():
        raise SystemExit(f"ROI CSV not found: {roi_path}")
    if not clutch_path.exists():
        raise SystemExit(f"Clutches CSV not found: {clutch_path}")

    df_roi = pd.read_csv(roi_path)
    df_clutches = pd.read_csv(clutch_path)

    if "legacy_clutch_key" not in df_roi.columns:
        raise SystemExit("ROI CSV missing 'legacy_clutch_key'")
    for col in ["legacy_clutch_key", "clutch_code"]:
        if col not in df_clutches.columns:
            raise SystemExit(f"legacy_clutches_v9.csv missing '{col}'")

    # Map legacy_clutch_key → clutch_code
    key_to_code: Dict[str, str] = {}
    for _, row in df_clutches.iterrows():
        key = str(row["legacy_clutch_key"])
        code = str(row["clutch_code"]).strip()
        if not code:
            continue
        key_to_code[key] = code

    # Ensure slug column exists
    if "genotype_base_codes_slug" not in df_roi.columns:
        raise SystemExit("ROI CSV missing 'genotype_base_codes_slug' column")

    df_roi["legacy_clutch_key"] = df_roi["legacy_clutch_key"].fillna("").astype(str)

    # Aggregate basecodes per clutch_code from slug column
    clutch_to_basecodes: Dict[str, set] = {}
    for _, row in df_roi.iterrows():
        key = row["legacy_clutch_key"]
        clutch_code = key_to_code.get(key)
        if not clutch_code:
            continue
        slugs = split_slug(row.get("genotype_base_codes_slug"))
        if not slugs:
            continue
        s = clutch_to_basecodes.setdefault(clutch_code, set())
        for b in slugs:
            s.add(b)

    if not clutch_to_basecodes:
        print("[WARN] No genotype basecodes found in ROI CSV slugs.")
        return

    eng = get_engine()

    # Load constructs and map base_code → construct_id
    with eng.begin() as cx:
        df_con = pd.read_sql(
            text("SELECT id::uuid AS construct_id, base_code FROM public.constructs"),
            cx,
        )
        df_cl_db = pd.read_sql(
            text(
                """
                SELECT id::uuid AS clutch_id,
                       clutch_code,
                       genotype_v11_id
                FROM public.clutches
                WHERE source_system = 'legacy_imaging'
                """
            ),
            cx,
        )

    basecode_to_constructs: Dict[str, List[str]] = {}
    for _, row in df_con.iterrows():
        base = (row["base_code"] or "").strip()
        if not base:
            continue
        basecode_to_constructs.setdefault(base, []).append(str(row["construct_id"]))

    code_to_genotype: Dict[str, str] = {}
    for _, row in df_cl_db.iterrows():
        code = str(row["clutch_code"]).strip()
        gid = row["genotype_v11_id"]
        if not code or pd.isna(gid):
            continue
        code_to_genotype[code] = str(gid)

    rows = []
    for clutch_code, bases in clutch_to_basecodes.items():
        gid = code_to_genotype.get(clutch_code)
        if not gid:
            continue
        for b in bases:
            cids = basecode_to_constructs.get(b.strip())
            if not cids:
                continue
            for cid in cids:
                rows.append({"genotype_id": gid, "construct_id": cid})

    if not rows:
        print("[WARN] No genotype→construct rows to insert (no matching basecodes).")
        return

    df_rows = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["genotype_id", "construct_id"])
    )

    print(f"[INFO] Found {len(df_rows)} genotype→construct rows from CSV slugs.")

    with eng.begin() as cx:
        for r in df_rows.itertuples(index=False):
            cx.execute(
                text(
                    """
                    INSERT INTO public.join_genotype_constructs_v11 (genotype_id, construct_id)
                    VALUES (:gid, :cid)
                    ON CONFLICT (genotype_id, construct_id) DO NOTHING;
                    """
                ),
                {"gid": r.genotype_id, "cid": r.construct_id},
            )

    print("[OK] Seeded join_genotype_constructs_v11 from v9 CSV slugs.")


if __name__ == "__main__":
    main()
