# Legacy imaging pipeline contract: no derived garbage

## Canonical construct code
Constructs are canonicalized as: `prefix-int`
- lowercase
- dash separator
- no leading zeros
Examples:
- pdqm034 → pdqm-34
- pDQM005 → pdqm-5
- MGCO-01 → mgco-1
- pswin04 → pswin-4

## Hard rule: DB writes must be FK-backed
Any loader that creates/updates genotypes MUST:
1. Normalize every token to canonical form
2. Resolve every token to `public.constructs.id`
3. Insert `public.join_genotype_constructs_v11` rows
4. Refuse to write if any token does not resolve

## Hard rule: RAW-only provenance
`seed_kits/legacy_wrangling_v2/raw/` is the only source of truth.
Anything in `legacy_wrangling_v2/working` or `legacy_wrangling_v2/final` is derived and MUST NOT be used to feed the DB.

## Explicit invariant
Derived outputs MUST NOT contain pSWIN04/pSWIN05 unless present in RAW and mapped deterministically to canonical constructs.
