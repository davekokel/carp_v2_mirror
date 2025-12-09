from __future__ import annotations

from typing import Literal


InstanceConstructKind = Literal[
    "background",
    "treated_only",
    "transgenic",
    "transgenic_and_treated",
]

ClutchGenotypeMixKind = Literal[
    "single_genotype",
    "mixed_genotypes",
]


def classify_instance_construct_kind(
    has_genotype_constructs: bool,
    has_treatment_constructs: bool,
) -> InstanceConstructKind:
    if not has_genotype_constructs and not has_treatment_constructs:
        return "background"
    if not has_genotype_constructs and has_treatment_constructs:
        return "treated_only"
    if has_genotype_constructs and not has_treatment_constructs:
        return "transgenic"
    return "transgenic_and_treated"


def classify_clutch_mix_kind(
    n_distinct_expected_genotypes: int,
) -> ClutchGenotypeMixKind:
    if n_distinct_expected_genotypes <= 1:
        return "single_genotype"
    return "mixed_genotypes"
