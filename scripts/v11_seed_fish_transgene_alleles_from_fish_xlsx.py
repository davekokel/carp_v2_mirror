#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Tuple, Optional, List

import pandas as pd
from sqlalchemy import create_engine, text


FISH_XLSX = "seed_kits/2025-11-15-121231-autoload/fish.xlsx"


def norm(s: object) -> str:
    if s is None:
        return ""
    return str(s).strip()


def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)


def load_line_to_allele_mapping(path: Path) -> Dict[Tuple[str, str, str], Optional[str]]:
    df = pd.read_excel(path)
    cols = {
        "nickname",
        "genetic_background",
        "transgene_base_code",
        "allele_nickname",
    }
    missing = cols - set(df.columns)
    if missing:
        raise SystemExit(
            f"[v11_seed_fish_transgene_alleles_from_fish_xlsx] missing columns in fish.xlsx: {sorted(missing)}"
        )

    df = df.copy()
    df["nickname"] = df["nickname"].map(norm)
    df["genetic_background"] = df["genetic_background"].map(norm)
    df["transgene_base_code"] = df["transgene_base_code"].map(norm)
    df["allele_nickname"] = df["allele_nickname"].map(
        lambda x: norm(x) if norm(x) and norm(x).lower() != "nan" else ""
    )

    df = df[df["transgene_base_code"] != ""].copy()

    lut: Dict[Tuple[str, str, str], Optional[str]] = {}

    rows: List[Tuple[Tuple[str, str, str], str]] = []
    for _, r in df.iterrows():
        key = (
            r["nickname"],
            r["genetic_background"],
            r["transgene_base_code"],
        )
        rows.append((key, r["allele_nickname"]))

    for key, nick in rows:
        if nick:
            prev = lut.get(key)
            if prev is not None and prev != nick:
                print(
                    "[v11_seed_fish_transgene_alleles_from_fish_xlsx] WARN: conflicting allele_nickname for line key",
                    key,
                    "existing=",
                    prev,
                    "new=",
                    nick,
                    "; keeping existing and skipping new.",
                )
                continue
            lut[key] = nick

    for key, nick in rows:
        if key not in lut and not nick:
            lut[key] = None

    return lut


def main():
    engine = get_engine()
    path = Path(FISH_XLSX)
    if not path.exists():
        raise SystemExit(
            f"[v11_seed_fish_transgene_alleles_from_fish_xlsx] fish.xlsx not found: {path}"
        )

    line_to_allele = load_line_to_allele_mapping(path)

    with engine.begin() as cx:
        df_lines = pd.read_sql(
            text(
                """
                SELECT
                  id::text                AS line_id,
                  line_code,
                  nickname,
                  genetic_background,
                  construct_code
                FROM public.fish_lines
                """
            ),
            cx,
        )

    df_lines["nickname"] = df_lines["nickname"].map(norm)
    df_lines["genetic_background"] = df_lines["genetic_background"].map(norm)
    df_lines["construct_code"] = df_lines["construct_code"].map(norm)

    inserted_links = 0
    missing_alleles: set[Tuple[str, Optional[str]]] = set()

    with engine.begin() as cx:
        df_instances = pd.read_sql(
            text(
                """
                SELECT
                  id::text AS fish_id,
                  line_id::text AS line_id
                FROM public.fish_instances_v10
                """
            ),
            cx,
        )
        instances_by_line: Dict[str, list[str]] = {}
        for _, r in df_instances.iterrows():
            instances_by_line.setdefault(r["line_id"], []).append(r["fish_id"])

        for _, line in df_lines.iterrows():
            line_id = line["line_id"]
            base_code = line["construct_code"]
            nick = line["nickname"]
            bg = line["genetic_background"]

            if not base_code:
                continue

            key = (nick, bg, base_code)
            allele_nick = line_to_allele.get(key)

            res = cx.execute(
                text(
                    """
                    SELECT
                      allele_number
                    FROM public.transgene_alleles
                    WHERE transgene_base_code = :bc
                      AND (:anick IS NULL OR allele_nickname = :anick)
                    ORDER BY allele_number
                    LIMIT 1
                    """
                ),
                {"bc": base_code, "anick": allele_nick},
            ).fetchone()

            if res is None:
                missing_alleles.add((base_code, allele_nick))
                continue

            allele_number = int(res[0])
            fish_ids = instances_by_line.get(line_id, [])
            if not fish_ids:
                continue

            for fid in fish_ids:
                r2 = cx.execute(
                    text(
                        """
                        INSERT INTO public.fish_transgene_alleles (
                          fish_id,
                          transgene_base_code,
                          allele_number
                        )
                        VALUES (:fid, :bc, :anum)
                        ON CONFLICT (fish_id, transgene_base_code, allele_number) DO NOTHING;
                        """
                    ),
                    {"fid": fid, "bc": base_code, "anum": allele_number},
                )
                inserted_links += r2.rowcount

    if missing_alleles:
        print(
            "[v11_seed_fish_transgene_alleles_from_fish_xlsx] WARN: no transgene_alleles row for (base_code, allele_nick):",
            "; ".join(f"{bc}:{anick}" for bc, anick in sorted(missing_alleles)),
        )

    print(
        f"[v11_seed_fish_transgene_alleles_from_fish_xlsx] inserted {inserted_links} fish_transgene_alleles links"
    )


if __name__ == "__main__":
    main()
