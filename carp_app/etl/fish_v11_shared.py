from __future__ import annotations

"""
Compatibility shim for v11 fish helpers.

New code should import from:

  - carp_app.etl.fish_v11_core   (DB-level primitives)
  - carp_app.etl.fish_v11_import (CSV loaders)

This module re-exports those functions so older scripts/pages keep working.
Do NOT add new logic here.
"""

from .fish_v11_core import (
    _norm,
    _coerce_date,
    load_construct_ids,
    ensure_allele_new_or_existing,
    ensure_group_and_genotype_for_alleles,
    ensure_line_for_description,
    ensure_tank_for_instance,
    _create_instances_with_genotype_and_bg as create_instances_with_genotype_and_bg,
)

from .fish_v11_import import load_fish_from_csv
