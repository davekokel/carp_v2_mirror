#!/usr/bin/env python3
from __future__ import annotations
import os
from sqlalchemy import create_engine, text

def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)

def main():
    engine = get_engine()
    with engine.begin() as cx:
        res = cx.execute(
            text(
                """
                INSERT INTO public.join_fish_transgene_alleles (
                  id,
                  fish_id,
                  transgene_base_code,
                  allele_number,
                  zygosity,
                  created_at
                )
                SELECT
                  gen_random_uuid(),
                  fi.id,
                  la.transgene_base_code,
                  la.allele_number,
                  la.zygosity,
                  now()
                FROM public.fish_instances_v10 fi
                JOIN public.join_fish_transgene_alleles_line la
                  ON la.line_id = fi.line_id
                ON CONFLICT DO NOTHING
                """
            )
        )
        print(f"v11_seed_fish_alleles_from_genotypes: inserted {res.rowcount} row(s)")
