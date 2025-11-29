from __future__ import annotations

import os
from typing import Dict, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DB_URL")

LEGACY_CLUTCHES_CSV = "seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9.csv"
OVERRIDES_CSV = "seed_kits/legacy_wrangling_v2/working/legacy_parent_line_overrides_v11.csv"


def _norm(s: str) -> str:
    return (s or "").strip()


def main() -> None:
    if not DB_URL:
        raise RuntimeError("DB_URL is not set")

    engine = create_engine(DB_URL)

    # 1) Base nickname → (line_id, allele_canonical)
    with engine.begin() as cx:
        nick_df = pd.read_sql(
            text(
                """
                WITH la AS (
                  SELECT
                    line_id,
                    allele_canonical_rollup
                  FROM public.v11_line_allele_rollups
                )
                SELECT
                  fl.nickname::text       AS nickname,
                  fl.id::text             AS line_id,
                  COALESCE(la.allele_canonical_rollup, '')::text AS allele_canonical
                FROM public.fish_lines fl
                LEFT JOIN la ON la.line_id = fl.id
                """
            ),
            cx,
        )

    nick_map: Dict[str, Tuple[str, str]] = {}
    for _, row in nick_df.iterrows():
        nick = _norm(row["nickname"])
        if not nick:
            continue
        line_id = str(row["line_id"])
        allele_canonical = _norm(row["allele_canonical"])
        nick_map[nick] = (line_id, allele_canonical)

    print(f"[INFO] Nickname → line mapping rows: {len(nick_map)}")

    # 2) Optional overrides: parent_label → line_nickname → canonical allele
    override_map: Dict[str, Tuple[str, str]] = {}
    if os.path.exists(OVERRIDES_CSV):
        ov = pd.read_csv(OVERRIDES_CSV)
        if not {"parent_label", "line_nickname"}.issubset(ov.columns):
            raise ValueError(f"{OVERRIDES_CSV} must have parent_label,line_nickname columns")
        for _, row in ov.iterrows():
            label = _norm(str(row["parent_label"] or ""))
            ln = _norm(str(row["line_nickname"] or ""))
            if not label or not ln:
                continue
            if ln not in nick_map:
                print(f"[WARN] override line_nickname '{ln}' not in fish_lines; skipping override for '{label}'")
                continue
            override_map[label] = nick_map[ln]
        print(f"[INFO] Loaded {len(override_map)} parent_label overrides")
    else:
        print(f"[INFO] No overrides file found at {OVERRIDES_CSV}; skipping overrides")

    # 3) Load legacy clutch CSV
    if not os.path.exists(LEGACY_CLUTCHES_CSV):
        raise FileNotFoundError(f"Legacy clutch CSV not found: {LEGACY_CLUTCHES_CSV}")
    cl_csv = pd.read_csv(LEGACY_CLUTCHES_CSV)
    if "clutch_code" not in cl_csv.columns:
        raise ValueError(f"{LEGACY_CLUTCHES_CSV} must have a 'clutch_code' column")

    updated = 0
    skipped_existing = 0
    skipped_no_parents = 0
    skipped_missing_clutch = 0

    with engine.begin() as cx:
        for _, row in cl_csv.iterrows():
            clutch_code = _norm(str(row.get("clutch_code") or ""))
            if not clutch_code:
                continue

            mom_label = _norm(str(row.get("parent_female_genotype_text") or ""))
            dad_label = _norm(str(row.get("parent_male_genotype_text") or ""))

            # Look up clutch in DB
            db_row = pd.read_sql(
                text(
                    """
                    SELECT
                      id::text                       AS clutch_id,
                      COALESCE(genotype_base_codes,'')::text AS genotype_base_codes
                    FROM public.clutches
                    WHERE clutch_code = :code
                      AND source_system = 'legacy_imaging'
                    LIMIT 1
                    """
                ),
                cx,
                params={"code": clutch_code},
            )

            if db_row.empty:
                skipped_missing_clutch += 1
                continue

            clutch_id = db_row["clutch_id"].iloc[0]
            current_codes = _norm(db_row["genotype_base_codes"].iloc[0])

            if current_codes:
                skipped_existing += 1
                continue

            mom_canonical = ""
            dad_canonical = ""

            # mom
            if mom_label:
                if mom_label in override_map:
                    _, mom_canonical = override_map[mom_label]
                elif mom_label in nick_map:
                    _, mom_canonical = nick_map[mom_label]

            # dad
            if dad_label:
                if dad_label in override_map:
                    _, dad_canonical = override_map[dad_label]
                elif dad_label in nick_map:
                    _, dad_canonical = nick_map[dad_label]

            mom_canonical = _norm(mom_canonical)
            dad_canonical = _norm(dad_canonical)

            if not mom_canonical and not dad_canonical:
                skipped_no_parents += 1
                continue

            if mom_canonical and dad_canonical:
                geno_code = f"{mom_canonical} × {dad_canonical}"
            else:
                geno_code = mom_canonical or dad_canonical

            cx.execute(
                text(
                    """
                    UPDATE public.clutches
                    SET
                      genotype_base_codes   = :geno,
                      genotype_allele_codes = NULL,
                      genotype_pretty       = :geno
                    WHERE id = CAST(:cid AS uuid)
                    """
                ),
                {"geno": geno_code, "cid": clutch_id},
            )
            updated += 1
            print(f"[UPDATE] {clutch_code}: genotype_base_codes = {geno_code}")

    print(f"[OK] Updated genotypes for {updated} clutch(es).")
    print(f"[INFO] Skipped (already had genotype_base_codes): {skipped_existing}")
    print(f"[INFO] Skipped (no resolvable parents even after overrides): {skipped_no_parents}")
    print(f"[INFO] Skipped (clutch_code not found in DB): {skipped_missing_clutch}")


if __name__ == "__main__":
    main()
