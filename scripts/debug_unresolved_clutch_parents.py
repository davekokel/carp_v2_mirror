from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text
import os

DB_URL = os.getenv("DB_URL")
LEGACY_CLUTCHES_CSV = "seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9.csv"

def _norm(s: str) -> str:
    return (s or "").strip()

def main() -> None:
    if not DB_URL:
        raise RuntimeError("DB_URL is not set")

    engine = create_engine(DB_URL)

    # load fish_lines nicknames
    with engine.begin() as cx:
        fl = pd.read_sql(
            text("SELECT nickname::text AS nickname FROM public.fish_lines"),
            cx,
        )

    all_nicks = sorted({_norm(n) for n in fl["nickname"].tolist() if _norm(n)})

    # load legacy clutch CSV
    if not os.path.exists(LEGACY_CLUTCHES_CSV):
        raise FileNotFoundError(f"Legacy clutch CSV not found: {LEGACY_CLUTCHES_CSV}")
    df = pd.read_csv(LEGACY_CLUTCHES_CSV)

    # load current clutch genotypes from DB
    with engine.begin() as cx:
        db_cl = pd.read_sql(
            text(
                """
                SELECT
                  clutch_code::text AS clutch_code,
                  COALESCE(genotype_base_codes,'')::text AS genotype_base_codes
                FROM public.clutches
                WHERE source_system = 'legacy_imaging'
                """
            ),
            cx,
        )

    geno_map = {row["clutch_code"]: _norm(row["genotype_base_codes"]) for _, row in db_cl.iterrows()}

    rows = []
    for _, r in df.iterrows():
        clutch_code = _norm(str(r.get("clutch_code") or ""))
        mom = _norm(str(r.get("parent_female_genotype_text") or ""))
        dad = _norm(str(r.get("parent_male_genotype_text") or ""))
        current = geno_map.get(clutch_code, "")
        if current:
            continue  # already resolved

        if not mom and not dad:
            continue  # nothing to resolve

        rows.append((clutch_code, mom, dad))

    if not rows:
        print("[INFO] All legacy clutches with parents have genotype_base_codes.")
        return

    print(f"[INFO] Legacy clutches with unresolved parent nicknames: {len(rows)}\n")

    def suggest(nick: str) -> list[str]:
        if not nick:
            return []
        first = nick.split()[0]
        candidates = [n for n in all_nicks if n.startswith(first)]
        return candidates[:5]

    for clutch_code, mom, dad in rows:
        print(f"Clutch {clutch_code}:")
        if mom:
            print(f"  mom={mom}")
            cand = suggest(mom)
            if cand:
                print(f"    candidates: {cand}")
            else:
                print("    candidates: (none)")
        if dad:
            print(f"  dad={dad}")
            cand = suggest(dad)
            if cand:
                print(f"    candidates: {cand}")
            else:
                print("    candidates: (none)")
        print()

if __name__ == "__main__":
    main()
