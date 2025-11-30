from __future__ import annotations

import sys
import pathlib

from sqlalchemy import text
from sqlalchemy.engine import Engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.lib.app_ctx import get_engine


def _eng() -> Engine:
    return get_engine()


def seed_fish_alleles_from_lines() -> None:
    eng = _eng()

    with eng.begin() as cx:
        cx.execute(text("DELETE FROM public.fish_transgene_alleles;"))

    sql = text(
        """
        INSERT INTO public.fish_transgene_alleles (
          fish_id,
          transgene_base_code,
          allele_number
        )
        SELECT DISTINCT
          fi.id          AS fish_id,
          c.base_code    AS transgene_base_code,
          jla.allele_number
        FROM public.fish_instances_v10 fi
        JOIN public.fish_lines fl
          ON fl.id = fi.line_id
        JOIN public.join_line_alleles jla
          ON jla.line_id = fl.id
        JOIN public.constructs c
          ON c.id = jla.construct_id
        JOIN public.transgene_alleles ta
          ON ta.transgene_base_code = c.base_code
         AND ta.allele_number       = jla.allele_number;
        """
    )

    with eng.begin() as cx:
        cx.execute(sql)

    print("v11_seed_fish_alleles_from_genotypes: seeded fish_transgene_alleles from line alleles.")


if __name__ == "__main__":
    seed_fish_alleles_from_lines()
