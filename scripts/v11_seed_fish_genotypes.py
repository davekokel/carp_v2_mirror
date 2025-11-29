#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import pandas as pd
import pathlib, sys

# repo root
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.engine import Engine
from carp_app.ui.lib.app_ctx import get_engine


def stable_code(basecodes: str) -> str:
    """Deterministic stable hash for genotype_v11_code (fish)."""
    basecodes = (basecodes or "").strip()
    h = hashlib.sha1(basecodes.encode("utf-8")).hexdigest()[:10].upper()
    return f"G-FISH-{h}"


def main():
    eng: Engine = get_engine()

    # ─────────────────────────────────────────────
    # Load fish instances from v11_fish_instance_star
    # ─────────────────────────────────────────────
    sql = """
        SELECT
          fish_instance_id AS id,
          fish_code,
          genotype_pretty,
          genotype_basecode_code
        FROM public.v11_fish_instance_star
    """

    with eng.begin() as cx:
        df = pd.read_sql(sql, cx)

    upserted = 0
    assigned = 0

    for row in df.itertuples(index=False):
        raw = row.genotype_basecode_code or ""
        tokens = [x.strip() for x in raw.split("||") if x.strip()]
        tokens = sorted(set(tokens))
        canonical = "||".join(tokens)

        pretty = row.genotype_pretty or ""

        if canonical:
            code = stable_code(canonical)
        else:
            code = "G-FISH-EMPTY"

        with eng.begin() as cx:
            # upsert genotype definition
            cx.execute(
                text("""
                INSERT INTO public.genotypes_v11_fish
                    (genotype_code, genotype_pretty, genotype_basecodes)
                VALUES (:code, :pretty, :basecodes)
                ON CONFLICT (genotype_code) DO NOTHING;
                """),
                {"code": code, "pretty": pretty, "basecodes": canonical},
            )
            upserted += 1

            # assign to fish instance
            cx.execute(
                text("""
                UPDATE public.fish_instances_v10 fi
                SET genotype_v11_id = g.id
                FROM public.genotypes_v11_fish g
                WHERE fi.id = :fid
                  AND g.genotype_code = :code;
                """),
                {"fid": row.id, "code": code},
            )
            assigned += 1

    print(f"[OK] Upserted {upserted} fish genotype definitions.")
    print(f"[OK] Assigned genotype_v11_id for {assigned} fish instances.")


if __name__ == "__main__":
    main()
