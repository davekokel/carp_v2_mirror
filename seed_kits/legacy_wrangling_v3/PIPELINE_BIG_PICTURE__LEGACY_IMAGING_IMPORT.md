# Legacy imaging import — big picture plan (no circles)

This doc is the contract + architecture for importing legacy imaging data so it appears correctly in the ROI flat page
(`carp_app/ui/pages/620_🔬_roi_flat_table.py`, view `public.v_roi_overview_rollups`).

## Goal
- Import legacy imaging ROIs + clutch memberships + legacy clutches + treatments + genotypes
- Ensure ROI flat page shows **correct genotype/treatment display fields**
- Ensure we **never write derived garbage** into the DB again

## Invariants (hard rules)
### 1) Canonical construct code format (database-level truth)
Constructs in `public.constructs.base_code` are canonical:
- lowercase
- `prefix-int`
- dash separator
- no leading zeros

Examples:
- `pDQM005` → `pdqm-5`
- `PDQM034` → `pdqm-34`
- `MGCO-01` → `mgco-1`

### 2) Token normalization is centralized
All code that parses or normalizes construct tokens MUST use:
- `carp_app/pipelines/construct_tokens.py`
  - `canonicalize_token(s)`
  - `canonicalize_tokens(s)`
  - `resolve_construct_ids(engine, canonical_tokens)`

No other bespoke regexes. No silent fallbacks.

### 3) DB writes involving genotype constructs are FK-backed
Whenever a loader creates/updates genotypes for construct-based genotypes:
- canonicalize tokens
- resolve tokens to `public.constructs.id`
- write links to `public.join_genotype_constructs_v11`
- STOP if any token does not resolve

### 4) Provenance / inputs are explicit and config-driven
No script hardcodes CSV paths.
Every loader reads a single config file (repo-relative paths), e.g.
`seed_kits/legacy_wrangling_v3/legacy_imaging_config.toml` (or `.yaml`), defining:
- raw inputs (xlsx/csv)
- working outputs
- expected batch ids
- active pipeline version (v3/v9/v11)

### 5) Derived outputs never become inputs unless explicitly allowed
The pipeline distinguishes:
- RAW: source-of-truth inputs
- WORKING: generated intermediate artifacts
- DB: the only place that should be “truth” after load

Any script that loads to DB must log:
- exact input path(s)
- git commit hash (if available)
- row counts and key uniqueness counts
- and must fail on invariant violations

## The 4-person team workflow
### Detective
- Reads code + traces data flow end-to-end
- Writes hypotheses about what is happening (no changes)

### Verifier
- Produces concrete commands (psql/python/rg) for Dave to run
- Only forwards verified facts to Designer/Builder

### Designer
- Proposes minimal, stable architecture changes
- Must reference verifier facts (tables/fields/row counts)

### Builder
- Implements only what Designer specifies
- Uses heredocs for new files
- Uses full 0-indent replacement blocks for patches
- Never patches without seeing the exact current code section first

## Current known failure mode (example)
“Derived garbage” genotypes like `pSWIN04/pSWIN05` appeared because:
- upstream parent definitions allowed those tokens
- genotypes were created and clutches pointed at them
Fix pattern:
1) fix the loader that produced the bad tokens (strict canonicalization + FK resolution)
2) remove stale DB artifacts and re-run the corrected loaders to regenerate clean data
   (this is not “manual backfill”; it is replaying the pipeline deterministically)

## Next engineering steps (high-level)
1) Add `legacy_imaging_config.toml`
2) Update legacy loaders to read config (no hardcoded file paths)
3) Add a single `scripts/legacy_imaging_run_pipeline.py` that:
   - runs steps in order
   - enforces invariants after each step
4) Ensure genotype loaders always populate `join_genotype_constructs_v11`
5) Only then: rebuild rollup views / ROI flat page display logic

MDcd ~/Projects/carp_v2
cat > seed_kits/legacy_wrangling_v3/PIPELINE_BIG_PICTURE__LEGACY_IMAGING_IMPORT.md <<'MD'
# Legacy imaging import — big picture plan (no circles)

This doc is the contract + architecture for importing legacy imaging data so it appears correctly in the ROI flat page
(`carp_app/ui/pages/620_🔬_roi_flat_table.py`, view `public.v_roi_overview_rollups`).

## Goal
- Import legacy imaging ROIs + clutch memberships + legacy clutches + treatments + genotypes
- Ensure ROI flat page shows **correct genotype/treatment display fields**
- Ensure we **never write derived garbage** into the DB again

## Invariants (hard rules)
### 1) Canonical construct code format (database-level truth)
Constructs in `public.constructs.base_code` are canonical:
- lowercase
- `prefix-int`
- dash separator
- no leading zeros

Examples:
- `pDQM005` → `pdqm-5`
- `PDQM034` → `pdqm-34`
- `MGCO-01` → `mgco-1`

### 2) Token normalization is centralized
All code that parses or normalizes construct tokens MUST use:
- `carp_app/pipelines/construct_tokens.py`
  - `canonicalize_token(s)`
  - `canonicalize_tokens(s)`
  - `resolve_construct_ids(engine, canonical_tokens)`

No other bespoke regexes. No silent fallbacks.

### 3) DB writes involving genotype constructs are FK-backed
Whenever a loader creates/updates genotypes for construct-based genotypes:
- canonicalize tokens
- resolve tokens to `public.constructs.id`
- write links to `public.join_genotype_constructs_v11`
- STOP if any token does not resolve

### 4) Provenance / inputs are explicit and config-driven
No script hardcodes CSV paths.
Every loader reads a single config file (repo-relative paths), e.g.
`seed_kits/legacy_wrangling_v3/legacy_imaging_config.toml` (or `.yaml`), defining:
- raw inputs (xlsx/csv)
- working outputs
- expected batch ids
- active pipeline version (v3/v9/v11)

### 5) Derived outputs never become inputs unless explicitly allowed
The pipeline distinguishes:
- RAW: source-of-truth inputs
- WORKING: generated intermediate artifacts
- DB: the only place that should be “truth” after load

Any script that loads to DB must log:
- exact input path(s)
- git commit hash (if available)
- row counts and key uniqueness counts
- and must fail on invariant violations

## The 4-person team workflow
### Detective
- Reads code + traces data flow end-to-end
- Writes hypotheses about what is happening (no changes)

### Verifier
- Produces concrete commands (psql/python/rg) for Dave to run
- Only forwards verified facts to Designer/Builder

### Designer
- Proposes minimal, stable architecture changes
- Must reference verifier facts (tables/fields/row counts)

### Builder
- Implements only what Designer specifies
- Uses heredocs for new files
- Uses full 0-indent replacement blocks for patches
- Never patches without seeing the exact current code section first

## Current known failure mode (example)
“Derived garbage” genotypes like `pSWIN04/pSWIN05` appeared because:
- upstream parent definitions allowed those tokens
- genotypes were created and clutches pointed at them
Fix pattern:
1) fix the loader that produced the bad tokens (strict canonicalization + FK resolution)
2) remove stale DB artifacts and re-run the corrected loaders to regenerate clean data
   (this is not “manual backfill”; it is replaying the pipeline deterministically)

## Next engineering steps (high-level)
1) Add `legacy_imaging_config.toml`
2) Update legacy loaders to read config (no hardcoded file paths)
3) Add a single `scripts/legacy_imaging_run_pipeline.py` that:
   - runs steps in order
   - enforces invariants after each step
4) Ensure genotype loaders always populate `join_genotype_constructs_v11`
5) Only then: rebuild rollup views / ROI flat page display logic

