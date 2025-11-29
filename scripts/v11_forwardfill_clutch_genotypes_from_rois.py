from __future__ import annotations

import os, sys, pathlib
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.lib.app_ctx import get_engine  # type: ignore


TARGET_CLUTCHES: Sequence[str] = ("LCL-0003", "LCL-0005", "LCL-0007")
GENO = "Tg(PDQM-034)gu309"


def main() -> None:
    url = os.getenv("DB_URL")
    if not url:
        print("[ERR] DB_URL not set")
        return

    eng: Engine = get_engine()

    with eng.begin() as cx:
        done = cx.execute(
            text(
                """
                UPDATE public.clutches c
                SET
                  genotype_base_codes   = :g,
                  genotype_allele_codes = NULL,
                  genotype_pretty       = :g
                WHERE c.clutch_code = ANY(:codes)
                  AND COALESCE(genotype_base_codes, '') = ''
                """
            ),
            {"g": GENO, "codes": list(TARGET_CLUTCHES)},
        ).rowcount or 0

    print(f"[OK] Forward-filled genotype_base_codes='{GENO}' for {done} clutch(es).")


if __name__ == "__main__":
    main()
