from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Set

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.loaders import get_engine_from_env, normalize_base_code


def seed_transgenes_from_genotype_alleles(
    csv_path: str | Path,
    engine: Optional[Engine] = None,
) -> dict:
    """
    Seed public.transgenes and public.transgene_alleles from
    genotype_alleles_from_standard_fish.csv.

    Expected columns in CSV:
      - genotype_code
      - transgene_base_code
      - allele_nickname
      - zygosity

    Rules:
      - transgene_base_code is normalized via normalize_base_code.
      - Each distinct (base, allele_nickname) gets a canonical allele_number
        (1,2,3,...) per base, independent of the legacy nickname.
      - Legacy nickname is stored in allele_nickname.
      - allele_name = 'gu' || allele_number.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Genotype alleles CSV not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        return {
            "rows": 0,
            "transgenes_inserted": 0,
            "alleles_inserted": 0,
            "warnings": [],
        }

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["genotype_code", "transgene_base_code", "allele_nickname"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Genotype alleles CSV is missing required columns: {missing}")

    df["genotype_code"] = df["genotype_code"].astype(str).str.strip()
    df["transgene_base_code"] = df["transgene_base_code"].astype(str).str.strip()
    df["allele_nickname"] = df["allele_nickname"].astype(str).str.strip()
    df["zygosity"] = df.get("zygosity", "").astype(str).str.strip()

    mask_valid = (df["transgene_base_code"] != "") & (df["allele_nickname"] != "")
    df = df[mask_valid].reset_index(drop=True)

    if df.empty:
        return {
            "rows": 0,
            "transgenes_inserted": 0,
            "alleles_inserted": 0,
            "warnings": [],
        }

    if engine is None:
        engine = get_engine_from_env()

    warnings: List[str] = []
    transgenes_inserted = 0
    alleles_inserted = 0

    df["base_norm"] = df["transgene_base_code"].apply(normalize_base_code)

    # Insert transgenes (base only, description = base for now)
    bases = sorted({b for b in df["base_norm"] if b})
    with engine.begin() as cx:
        if bases:
            res = cx.execute(
                text(
                    """
                    INSERT INTO public.transgenes (transgene_base_code, description)
                    SELECT b, b
                    FROM unnest(:bases) AS b
                    ON CONFLICT (transgene_base_code) DO NOTHING
                    """
                ),
                {"bases": bases},
            )
            transgenes_inserted = res.rowcount or 0

    # Insert alleles with canonical numbers per base
    with engine.begin() as cx:
        # For each base, build desired nickname set
        per_base_nicks: Dict[str, Set[str]] = {}
        for _, row in df.iterrows():
            base = row["base_norm"]
            nick = row["allele_nickname"]
            if not base or not nick:
                continue
            per_base_nicks.setdefault(base, set()).add(nick)

        for base, nick_set in per_base_nicks.items():
            # Load existing alleles for this base (nickname -> allele_number)
            existing_rows = cx.execute(
                text(
                    """
                    SELECT allele_number, allele_nickname
                    FROM public.transgene_alleles
                    WHERE transgene_base_code = :b
                    """
                ),
                {"b": base},
            ).mappings().all()

            existing_by_nick: Dict[str, int] = {}
            used_numbers: Set[int] = set()
            for r in existing_rows:
                n = r["allele_number"]
                used_numbers.add(n)
                nn = r["allele_nickname"] or ""
                existing_by_nick[nn] = n

            # Deterministic order for new nicknames
            for nick in sorted(nick_set):
                if nick in existing_by_nick:
                    continue

                # allocate the smallest positive integer not used yet
                candidate = 1
                while candidate in used_numbers:
                    candidate += 1
                allele_number = candidate
                used_numbers.add(allele_number)
                allele_name = f"gu{allele_number}"

                res = cx.execute(
                    text(
                        """
                        INSERT INTO public.transgene_alleles
                          (transgene_base_code, allele_number, allele_name, allele_nickname, notes)
                        VALUES
                          (:b, :n, :aname, :nnick, :notes)
                        ON CONFLICT (transgene_base_code, allele_number) DO NOTHING
                        """
                    ),
                    {
                        "b": base,
                        "n": allele_number,
                        "aname": allele_name,
                        "nnick": nick,
                        "notes": "seeded from genotype_alleles_from_standard_fish.csv",
                    },
                )
                if res.rowcount and res.rowcount > 0:
                    alleles_inserted += 1

    return {
        "rows": len(df),
        "transgenes_inserted": transgenes_inserted,
        "alleles_inserted": alleles_inserted,
        "warnings": warnings,
    }
