from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.util import get_engine_from_env, normalize_base_code


def load_genotypes_from_csv(csv_path: str | Path, engine: Optional[Engine] = None) -> dict:
    """
    Load or upsert genotypes into public.genotypes from a CSV.

    Expected columns:
      - genotype_code
      - genotype_name
      - genetic_background
      - source_system
      - notes

    Upserts by genotype_code.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Genotypes CSV not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": []}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["genotype_code"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Genotypes CSV is missing required columns: {missing}")

    df["genotype_code"] = df["genotype_code"].astype(str).str.strip()
    df["genotype_name"] = df.get("genotype_name", "").astype(str).str.strip()
    df["genetic_background"] = df.get("genetic_background", "").astype(str).str.strip()
    df["source_system"] = df.get("source_system", "").astype(str).str.strip()
    df["notes"] = df.get("notes", "").astype(str).str.strip()

    mask_valid = df["genotype_code"].str.len() > 0
    df = df[mask_valid].reset_index(drop=True)

    if df.empty:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": []}

    if engine is None:
        engine = get_engine_from_env()

    codes = df["genotype_code"].unique().tolist()
    with engine.begin() as cx:
        existing = set(
            cx.execute(
                text(
                    "SELECT genotype_code FROM public.genotypes WHERE genotype_code = ANY(:codes)"
                ),
                {"codes": codes},
            ).scalars().all()
        )

    sql = text(
        """
        INSERT INTO public.genotypes
          (genotype_code, genotype_name, genetic_background, source_system, notes)
        VALUES
          (:code, NULLIF(:name,''), NULLIF(:bg,''), NULLIF(:source,''), NULLIF(:notes,''))
        ON CONFLICT (genotype_code) DO UPDATE
        SET genotype_name      = EXCLUDED.genotype_name,
            genetic_background = EXCLUDED.genetic_background,
            source_system      = EXCLUDED.source_system,
            notes              = EXCLUDED.notes
        """
    )

    inserted = 0
    updated = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            code = row["genotype_code"]
            params = {
                "code": code,
                "name": row.get("genotype_name", "") or "",
                "bg": row.get("genetic_background", "") or "",
                "source": row.get("source_system", "") or "",
                "notes": row.get("notes", "") or "",
            }
            cx.execute(sql, params)
            if code in existing:
                updated += 1
            else:
                inserted += 1
                existing.add(code)

    return {"rows": len(df), "inserted": inserted, "updated": updated, "warnings": []}


def load_genotype_alleles_from_csv(csv_path: str | Path, engine: Optional[Engine] = None) -> dict:
    """
    Load genotype_alleles_from_standard_fish.csv into public.join_genotype_transgene_alleles.

    Expected columns:
      - genotype_code
      - transgene_base_code
      - allele_nickname
      - zygosity

    Behavior:
      - Lookup genotype_id from public.genotypes by genotype_code.
      - Normalize transgene_base_code with normalize_base_code.
      - Resolve allele_number from public.transgene_alleles using
        (transgene_base_code, allele_nickname) matching either allele_nickname
        or allele_name.
      - Insert into join_genotype_transgene_alleles.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Genotype alleles CSV not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        return {"rows": 0, "links_created": 0, "warnings": []}

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

    mask_valid = (df["genotype_code"] != "") & (df["transgene_base_code"] != "") & (df["allele_nickname"] != "")
    df = df[mask_valid].reset_index(drop=True)

    if df.empty:
        return {"rows": 0, "links_created": 0, "warnings": []}

    if engine is None:
        engine = get_engine_from_env()

    warnings: list[str] = []
    links_created = 0

    with engine.begin() as cx:
        genotype_codes = df["genotype_code"].unique().tolist()
        geno_rows = cx.execute(
            text(
                "SELECT id, genotype_code FROM public.genotypes WHERE genotype_code = ANY(:codes)"
            ),
            {"codes": genotype_codes},
        ).mappings().all()
        geno_map = {r["genotype_code"]: r["id"] for r in geno_rows}

        for _, row in df.iterrows():
            g_code = row["genotype_code"]
            g_id = geno_map.get(g_code)
            if not g_id:
                warnings.append(f"Skipping genotype_allele row: genotype_code {g_code!r} not found.")
                continue

            base = normalize_base_code(row["transgene_base_code"])
            if not base:
                warnings.append(f"Skipping genotype_allele row for genotype_code {g_code!r}: empty base_code after normalization.")
                continue

            nick = row["allele_nickname"]
            allele_row = cx.execute(
                text(
                    """
                    SELECT transgene_base_code, allele_number
                    FROM public.transgene_alleles
                    WHERE transgene_base_code = :b
                      AND (allele_nickname = :n OR allele_name = :n)
                    LIMIT 1
                    """
                ),
                {"b": base, "n": nick},
            ).mappings().first()

            if not allele_row:
                warnings.append(
                    f"Skipping genotype_allele row: no transgene_alleles match for base={base!r}, allele_nickname={nick!r}."
                )
                continue

            allele_number = allele_row["allele_number"]
            zyg = row.get("zygosity", "") or None

            res = cx.execute(
                text(
                    """
                    INSERT INTO public.join_genotype_transgene_alleles
                      (genotype_id, transgene_base_code, allele_number, zygosity)
                    VALUES
                      (:gid, :b, :n, :zyg)
                    ON CONFLICT (genotype_id, transgene_base_code, allele_number)
                    DO UPDATE SET zygosity = COALESCE(EXCLUDED.zygosity, public.join_genotype_transgene_alleles.zygosity)
                    """
                ),
                {"gid": g_id, "b": base, "n": allele_number, "zyg": zyg},
            )
            if res.rowcount and res.rowcount > 0:
                links_created += 1

    return {"rows": len(df), "links_created": links_created, "warnings": warnings}
