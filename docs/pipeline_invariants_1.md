# Pipeline invariants v1

Date: 2025-12-26  
Scope: legacy imaging v4 pipeline (local/staging), clutch/genotype/treatment linking, ROI display rollups.

## Roles

### Pipeline architect
Owns the end-to-end ordering of steps and the contract between steps (files produced, schemas updated, and which steps may mutate DB state).

### Invariant owner
Defines what must always be true after each stage, and which failures are “hard stop” vs “report + skip.”

### Rule system designer
Encodes deterministic rules for mapping/overrides and ensures each rule is:
- explicit (documented, named)
- isolated (implemented in one place)
- testable (QC outputs, reproducible inputs)

## Hard rules

1. No “placeholder” strings may reach display outputs.
   - Any rendered genotype/tg string must be derived from a join to canonical tables, not by formatting guesses.

2. No silent inference across basecodes for allele nicknames.
   - Allele nicknames are only meaningful within a transgene_base_code.
   - Resolution must be done via (base_code, allele_nickname) or explicit per-row pairing.

3. No one-off manual DB edits as part of the pipeline.
   - If a manual SQL is needed to unblock, it must become a scripted step (checked into repo) with QC outputs.

4. Fail/skip policy must be explicit:
   - “Hard stop” only when continuing would corrupt identity/linkage.
   - Otherwise “report + skip” with counts and samples.

## Required QC outputs (minimum)

Each pipeline run must report and persist:

- counts of rows dropped by include_in_db
- counts of rows missing genotype_base_codes
- counts of rows missing treatment basecodes
- counts of mapping rows skipped for missing clutches
- counts of mapping rows ensured for missing treatments
- counts of ROIs with no markers and n_tiffs > 0

QC outputs must be written to a stable working directory with timestamps or batch ids, e.g.
`seed_kits/legacy_wrangling_v4/working/qc_runs/<run_id>/...`

