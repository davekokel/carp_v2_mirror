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


def norm(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _construct_key_variants(raw: str | None) -> set[str]:
    s = norm(raw)
    if not s:
        return set()

    keys: set[str] = set()
    keys.add(s)
    keys.add(s.lower())

    m = re.match(r"^([A-Za-z]+)[-_]?(0*)(\d+)$", s)
    if not m:
        return keys

    prefix = m.group(1).upper()
    digits = m.group(3)

    try:
        num = int(digits)
    except ValueError:
        return keys

    short = f"{prefix}-{num}"
    padded3 = f"{prefix}-{num:03d}"

    for v in (short, padded3):
        keys.add(v)
        keys.add(v.lower())

    return keys


def build_construct_lookup(engine: Engine) -> Dict[str, Tuple[str, str]]:
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

    lookup: Dict[str, Tuple[str, str]] = {}
    for _, row in df.iterrows():
        construct_id = norm(row["construct_id"])
        construct_code = norm(row["construct_code"])
        base_code = norm(row["base_code"])
        alias = norm(row.get("alias"))

        canon = construct_code or base_code
        if not canon:
            continue

        keys: set[str] = set()
        for raw in (construct_code, base_code, alias, canon):
            keys.update(_construct_key_variants(raw))

        for k in keys:
            if not k:
                continue
            lookup[k] = (construct_id, canon)

    print(f"[v10_load_treatments] construct lookup keys: {len(lookup)}")
    return lookup


def build_dye_lookup(engine: Engine) -> Dict[str, str]:
    """
    v11: build dye lookup from dyes.nickname (base code).
    Returns mapping from base_code (and lowercase) -> dye_id (as text).
    """
    sql = text(
        """
        SELECT id::text AS dye_id,
               nickname
        FROM public.dyes
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    lookup: Dict[str, str] = {}
    for _, row in df.iterrows():
        dye_id = norm(row["dye_id"])
        code = norm(row["nickname"])
        if not code:
            continue
        lookup[code] = dye_id
        lookup[code.lower()] = dye_id

    print(f"[v10_load_treatments] dye lookup keys: {len(lookup)}")
    return lookup


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: load treatments + mixes + ingredients from treatments CSV"
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to treatments_v10.csv",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"treatments CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
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
        raise SystemExit(
            f"treatments CSV missing required columns: {sorted(missing)}; "
            f"found {sorted(df.columns)}"
        )

    df = df.copy()
    for c in df.select_dtypes(include=["object", "string"]).columns:
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
          concentration,
          notes,
          created_at
        )
        VALUES (
          :mix_id,
          :ingredient_id,
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
          :ingredient_id,
          :concentration,
          NULL,
          now()
        )
        ON CONFLICT DO NOTHING
        """
    )

    inserted_treatments = 0
    inserted_mixes = 0
    inserted_constructs = 0
    inserted_dyes = 0
    skipped_ingredients = 0

    grouped = df.groupby(["treatment_code", "mix_code"], dropna=False)

    with engine.begin() as cx:
        for (t_code, mix_code), g in grouped:
            t_code = norm(t_code)
            mix_code = norm(mix_code)

            if not t_code:
                print("[v10_load_treatments] WARN: row with empty treatment_code; skipping group.")
                skipped_ingredients += len(g)
                continue

            t_name = norm(g["treatment_name"].iloc[0])
            kind_code = norm(g["kind_code"].iloc[0]) if "kind_code" in g.columns else ""
            t_notes = norm(g["treatment_notes"].iloc[0]) if "treatment_notes" in g.columns else ""
            mix_notes = norm(g["mix_notes"].iloc[0]) if "mix_notes" in g.columns else ""

            src = "legacy_v9" if "legacy" in t_code.lower() else "standard_seedkit"

            t_row = cx.execute(
                insert_treatment,
                {
                    "treat_code": t_code,
                    "kind_code": kind_code or None,
                    "treat_text": t_name or None,
                    "notes": t_notes or None,
                    "source_system": src,
                    "import_batch_id": "treatments_v10_seed",
                },
            ).fetchone()
            treatment_id = t_row._mapping["treatment_id"]
            inserted_treatments += 1

            m_row = cx.execute(
                insert_mix,
                {
                    "treatment_id": treatment_id,
                    "mix_code": mix_code or "default",
                    "notes": mix_notes or None,
                },
            ).fetchone()
            mix_id = m_row._mapping["mix_id"]
            inserted_mixes += 1

            for _, ing in g.iterrows():
                itype = norm(ing["ingredient_type"]).lower()
                code = norm(ing["ingredient_code"])
                conc = norm(ing["concentration"]) or None

                if not itype or not code:
                    skipped_ingredients += 1
                    continue

                if itype == "construct":
                    hit = (
                        construct_lookup.get(code)
                        or construct_lookup.get(code.lower())
                    )
                    if not hit:
                        print(
                            f"[v10_load_treatments] WARN: unknown construct ingredient_code={code!r} "
                            f"for treatment={t_code}, mix={mix_code}"
                        )
                        skipped_ingredients += 1
                        continue
                    construct_id, canon = hit
                    cx.execute(
                        insert_construct,
                        {
                            "mix_id": mix_id,
                            "ingredient_id": construct_id,
                            "concentration": conc,
                        },
                    )
                    inserted_constructs += 1

                elif itype == "dye":
                    dye_id = (
                        dye_lookup.get(code)
                        or dye_lookup.get(code.lower())
                    )
                    if not dye_id:
                        print(
                            f"[v10_load_treatments] WARN: unknown dye ingredient_code={code!r} "
                            f"for treatment={t_code}, mix={mix_code}"
                        )
                        skipped_ingredients += 1
                        continue
                    cx.execute(
                        insert_dye,
                        {
                            "mix_id": mix_id,
                            "ingredient_id": dye_id,
                            "concentration": conc,
                        },
                    )
                    inserted_dyes += 1

                else:
                    print(
                        f"[v10_load_treatments] WARN: unsupported ingredient_type={itype!r} "
                        f"(code={code!r}); skipping."
                    )
                    skipped_ingredients += 1

    print(f"[v10_load_treatments] upserted {inserted_treatments} treatment row(s)")
    print(f"[v10_load_treatments] upserted {inserted_mixes} treatment_mix row(s)")
    print(f"[v10_load_treatments] inserted {inserted_constructs} construct ingredients")
    print(f"[v10_load_treatments] inserted {inserted_dyes} dye ingredients")
    print(f"[v10_load_treatments] skipped {skipped_ingredients} ingredient row(s)")


if __name__ == "__main__":
    main()
