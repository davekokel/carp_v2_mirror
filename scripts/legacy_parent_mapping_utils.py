from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection

from carp_app.etl.code_normalization import normalize_base_code


def _is_casper_rnf(name: str | None) -> bool:
    if not name:
        return False
    # normalize spaces/case
    s = name.strip().lower().replace(" ", "")
    return "casper/rnf" in s


def resolve_casper_fish_ids(cx: Connection) -> List[str]:
    """
    Returns the list of casper fish_instance IDs.

    Rule from priming:
      • "casper/rnf" must be treated as "casper"
      • Map to the FIRST standard fish with genetic_background='casper'
    We implement that by returning IDs ordered by birthday (or code)
    and letting the caller decide whether to take the first or quarantine
    on ambiguity.
    """
    sql = text(
        """
        SELECT f.id
          FROM public.fish AS f
         WHERE f.genetic_background = 'casper'
         ORDER BY f.birthday NULLS LAST, f.fish_code
        """
    )
    rows = cx.execute(sql).fetchall()
    return [r[0] for r in rows]


def find_matching_alleles(
    cx: Connection, legacy_base_code: str, legacy_allele_nickname: str
) -> List[Dict]:
    """
    Legacy → canonical allele hop:
      • normalize_base_code(legacy_base_code) → transgene_base_code
      • legacy_allele_nickname == allele_nickname
    """
    norm_code = normalize_base_code(legacy_base_code or "")
    legacy_allele = (legacy_allele_nickname or "").strip()

    if not norm_code or not legacy_allele:
        return []

    sql = text(
        """
        SELECT ta.transgene_base_code,
               ta.allele_number,
               ta.allele_nickname
          FROM public.transgene_alleles AS ta
         WHERE ta.transgene_base_code = :norm_code
           AND ta.allele_nickname     = :legacy_allele
        """
    )
    rows = cx.execute(sql, {"norm_code": norm_code, "legacy_allele": legacy_allele}).mappings().all()
    return [dict(r) for r in rows]


def find_matching_fish_via_allele(
    cx: Connection, legacy_base_code: str, legacy_allele_nickname: str
) -> List[Dict]:
    """
    Canonical allele → fish_instance hop.

    Uses:
      • transgene_alleles (base_code, allele_number, allele_nickname)
      • join_fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
      • fish (id, fish_code)
    """
    norm_code = normalize_base_code(legacy_base_code or "")
    legacy_allele = (legacy_allele_nickname or "").strip()

    if not norm_code or not legacy_allele:
        return []

    sql = text(
        """
        WITH canonical AS (
            SELECT ta.transgene_base_code,
                   ta.allele_number,
                   ta.allele_nickname
              FROM public.transgene_alleles AS ta
             WHERE ta.transgene_base_code = :norm_code
               AND ta.allele_nickname     = :legacy_allele
        )
        SELECT DISTINCT f.id,
                        f.fish_code
          FROM canonical AS c
          JOIN public.join_fish_transgene_alleles AS jfta
            ON jfta.transgene_base_code = c.transgene_base_code
           AND jfta.allele_number       = c.allele_number
          JOIN public.fish AS f
            ON f.id = jfta.fish_id
        """
    )
    rows = cx.execute(sql, {"norm_code": norm_code, "legacy_allele": legacy_allele}).mappings().all()
    return [dict(r) for r in rows]


def debug_parent_match(
    cx: Connection,
    parent_fish_name: str,
    legacy_base_code: str,
    legacy_allele_nickname: str,
) -> Tuple[int, int]:
    """
    Returns:
      • n_matching_alleles
      • n_matching_fish

    Applies the casper/rnf override:
      • If parent looks like "casper/rnf", we do NOT require allele mapping.
      • Instead we look up casper fish by genetic_background='casper'.
    """
    if _is_casper_rnf(parent_fish_name):
        casper_ids = resolve_casper_fish_ids(cx)
        # For casper/rnf debugging:
        #   • alleles: treated as 0 (no specific transgene allele)
        #   • fish: number of casper fish candidates
        return 0, len(casper_ids)

    alleles = find_matching_alleles(cx, legacy_base_code, legacy_allele_nickname)
    fish = find_matching_fish_via_allele(cx, legacy_base_code, legacy_allele_nickname)
    return len(alleles), len(fish)


def resolve_parent_to_fish_ids(
    cx: Connection,
    parent_fish_name: str,
    legacy_base_code: str,
    legacy_allele_nickname: str,
) -> List[str]:
    """
    Main resolution helper for BOTH scripts:

    • If parent_fish_name contains "casper/rnf":
        → treat as casper
        → return ALL casper fish IDs (caller can decide how to handle >1).
    • Else:
        → use base_code + allele_nickname mapping via the canonical allele.
    """
    if _is_casper_rnf(parent_fish_name):
        return resolve_casper_fish_ids(cx)

    fish_rows = find_matching_fish_via_allele(cx, legacy_base_code, legacy_allele_nickname)
    return [row["id"] for row in fish_rows]
