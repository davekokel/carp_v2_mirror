#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Optional, Dict, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def norm(s: object) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _construct_key_variants(raw: str) -> set[str]:
    s = norm(raw)
    if not s:
        return set()

    keys: set[str] = {s, s.lower()}

    m = re.match(r"^([A-Za-z]+)[-_ ]?(0*)(\d+)$", s)
    if not m:
        return keys

    prefix = m.group(1).upper()
    digits = m.group(3)
    try:
        num = int(digits)
    except ValueError:
        return keys

    for v in (f"{prefix}-{num}", f"{prefix}-{num:03d}"):
        keys.add(v)
        keys.add(v.lower())

    # also accept no-dash forms like MGCO01
    keys.add(f"{prefix}{num}")
    keys.add(f"{prefix}{num}".lower())

    return keys


def build_construct_lookup(engine: Engine) -> Dict[str, str]:
    """
    Return mapping from many possible tokens -> construct_id (text uuid).
    Key idea: resolve the construct, but DO NOT use construct_kind/injection flags
    to determine delivery_form. delivery_form comes from CSV ingredient_type.
    """
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
        construct_id = norm(row["construct_id"])
        construct_code = norm(row.get("construct_code"))
        base_code = norm(row.get("base_code"))
        alias = norm(row.get("alias"))

        for raw in (construct_code, base_code, alias):
            for k in _construct_key_variants(raw):
                if k:
                    lookup[k] = construct_id

    print(f"[v10_load_treatments] construct lookup keys: {len(lookup)}")
    return lookup


def build_dye_lookup(engine: Engine) -> Dict[str, str]:
    """
    Map dye nickname/code/display_name -> dye_id (text uuid).
    """
    sql = text(
        """
        SELECT id::text AS dye_id,
               nickname,
               code,
               display_name
        FROM public.dyes
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    lut: Dict[str, str] = {}
    for _, r in df.iterrows():
        dye_id = norm(r["dye_id"])
        for raw in (r.get("nickname"), r.get("code"), r.get("display_name")):
            k = norm(raw)
            if not k:
                continue
            lut[k] = dye_id
            lut[k.lower()] = dye_id

    print(f"[v10_load_treatments] dye lookup keys: {len(lut)}")
    return lut


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: load treatments + mixes + ingredients from treatments CSV (STRICT: delivery_form comes from ingredient_type)"
    )
    parser.add_argument("--csv", required=True, help="Path to treatments_v10.csv")
    parser.add_argument("--db-url", help="Override DB_URL")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"treatments CSV not found: {csv_path}")

    df = pd.read_csv(csv_path, low_memory=False)
    print(f"[v10_load_treatments] read {len(df)} row(s) from {csv_path}")

    required_cols = {
        "treatment_code",
        "treatment_name",
        "mix_code",
        "ingredient_type",
        "ingredient_code",
        "concentration",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise SystemExit(f"treatments CSV missing required columns: {sorted(missing)}")

    # normalize strings
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype("string").fillna("").str.strip()

    engine = get_engine(args.db_url)
    construct_lookup = build_construct_lookup(engine)
    dye_lookup = build_dye_lookup(engine)

    insert_treatment = text(
        """
        INSERT INTO public.treatments (
          treat_code,
          kind_code,
          treat_text,
          notes,
          source_system,
          import_batch_id,
          created_at
        )
        VALUES (
          :treat_code,
          :kind_code,
          :treat_text,
          :notes,
          :source_system,
          :import_batch_id,
          now()
        )
        ON CONFLICT (treat_code) DO UPDATE SET
          kind_code       = EXCLUDED.kind_code,
          treat_text      = EXCLUDED.treat_text,
          notes           = EXCLUDED.notes,
          source_system   = EXCLUDED.source_system,
          import_batch_id = EXCLUDED.import_batch_id
        RETURNING id::text AS treatment_id
        """
    )

    insert_mix = text(
        """
        INSERT INTO public.treatment_mixes (
          treatment_id,
          mix_code,
          notes,
          created_at
        )
        VALUES (
          :treatment_id,
          :mix_code,
          :notes,
          now()
        )
        ON CONFLICT (treatment_id, mix_code) DO UPDATE SET
          notes = EXCLUDED.notes
        RETURNING id::text AS mix_id
        """
    )

    insert_construct = text(
        """
        INSERT INTO public.treatment_mix_constructs (
          mix_id,
          construct_id,
          delivery_form,
          concentration,
          notes,
          created_at
        )
        VALUES (
          :mix_id,
          :construct_id,
          :delivery_form,
          :concentration,
          NULL,
          now()
        )
        ON CONFLICT DO NOTHING
        """
    )

    insert_dye = text(
        """
        INSERT INTO public.treatment_mix_dyes (
          mix_id,
          dye_id,
          concentration,
          notes,
          created_at
        )
        VALUES (
          :mix_id,
          :dye_id,
          :concentration,
          NULL,
          now()
        )
        ON CONFLICT DO NOTHING
        """
    )

    allowed_construct_forms = {"plasmid", "rna", "crispr"}

    n_treatments = 0
    n_mixes = 0
    n_construct_ingredients = 0
    n_dye_ingredients = 0
    n_skipped = 0

    with engine.begin() as cx:
        for (treat_code, treat_name), df_treat in df.groupby(["treatment_code", "treatment_name"], dropna=False):
            treat_code = norm(treat_code)
            treat_name = norm(treat_name)
            if not treat_code:
                raise SystemExit("[STOP] blank treatment_code in CSV")

            treat_text = f"Injection of {treat_name or treat_code}"
            kind_code = "legacy_v10"
            notes = None
            source_system = "legacy_v10"
            import_batch_id = csv_path.name

            tr = cx.execute(
                insert_treatment,
                {
                    "treat_code": treat_code,
                    "kind_code": kind_code,
                    "treat_text": treat_text,
                    "notes": notes,
                    "source_system": source_system,
                    "import_batch_id": import_batch_id,
                },
            ).fetchone()
            treatment_id = tr[0]
            n_treatments += 1

            for mix_code, df_mix in df_treat.groupby(["mix_code"], dropna=False):
                mix_code = norm(mix_code)
                if not mix_code:
                    raise SystemExit(f"[STOP] blank mix_code for treatment_code={treat_code}")

                mr = cx.execute(
                    insert_mix,
                    {"treatment_id": treatment_id, "mix_code": mix_code, "notes": None},
                ).fetchone()
                mix_id = mr[0]
                n_mixes += 1

                for _, row in df_mix.iterrows():
                    ingredient_type = norm(row["ingredient_type"]).lower()
                    ingredient_code = norm(row["ingredient_code"])
                    concentration = norm(row.get("concentration"))

                    if not ingredient_type or not ingredient_code:
                        n_skipped += 1
                        continue

                    if ingredient_type == "dye":
                        dye_id = dye_lookup.get(ingredient_code) or dye_lookup.get(ingredient_code.lower())
                        if not dye_id:
                            raise SystemExit(
                                f"[STOP] unknown dye ingredient_code={ingredient_code!r} "
                                f"(treatment_code={treat_code}, mix_code={mix_code})"
                            )
                        cx.execute(
                            insert_dye,
                            {"mix_id": mix_id, "dye_id": dye_id, "concentration": concentration or None},
                        )
                        n_dye_ingredients += 1
                        continue

                    if ingredient_type not in allowed_construct_forms:
                        raise SystemExit(
                            f"[STOP] ingredient_type must be one of {sorted(allowed_construct_forms)} or 'dye'; "
                            f"got {ingredient_type!r} (treatment_code={treat_code}, mix_code={mix_code})"
                        )

                    construct_id = (
                        construct_lookup.get(ingredient_code)
                        or construct_lookup.get(ingredient_code.lower())
                    )
                    if not construct_id:
                        raise SystemExit(
                            f"[STOP] unknown construct ingredient_code={ingredient_code!r} "
                            f"(treatment_code={treat_code}, mix_code={mix_code})"
                        )

                    cx.execute(
                        insert_construct,
                        {
                            "mix_id": mix_id,
                            "construct_id": construct_id,
                            "delivery_form": ingredient_type,  # STRICT: comes from CSV
                            "concentration": concentration or None,
                        },
                    )
                    n_construct_ingredients += 1

    print(f"[v10_load_treatments] upserted {n_treatments} treatment row(s)")
    print(f"[v10_load_treatments] upserted {n_mixes} treatment_mix row(s)")
    print(f"[v10_load_treatments] inserted {n_construct_ingredients} construct ingredients")
    print(f"[v10_load_treatments] inserted {n_dye_ingredients} dye ingredients")
    print(f"[v10_load_treatments] skipped {n_skipped} ingredient row(s)")


if __name__ == "__main__":
    main()
