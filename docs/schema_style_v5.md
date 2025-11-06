# Schema Style (v5)

## Entities
- snake_case, plural when domain-collective (`fish`, `tanks`, `tags`, `dyes`), otherwise natural singular (`transgene_alleles`).
- PK: `id uuid DEFAULT gen_random_uuid()` unless a natural PK is explicit (e.g., `transgene_base_code`).

## Link tables (many-to-many)
- Name: `join_<a>_<b>` (alphabetical `<a>,<b>`).
- Columns: `<a>_id uuid NOT NULL` FK to `<a>(id)`, `<b>_id uuid NOT NULL` FK to `<b>(id)`.
- PK: `PRIMARY KEY (<a>_id, <b>_id)`.
- Metadata: `created_at timestamptz NOT NULL DEFAULT now()`.

## Lookup views
- Suffix `_lu`. Columns: `code`, `label`. No side effects.

## Rollup/overview views
- Prefix `v_`. Suffix `_by_ids` for PK-based rollups.
- One canonical overview view per domain (`v_fish_overview_id`).

## Constraint/index naming
- FK: `fk_<table>_<col>`
- Unique: `uq_<table>_<cols>`
- Index: `ix_<table>_<cols>`

## Column naming
- FKs to PK: `<entity>_id`. Code columns: `<entity>_code`.
- Use `created_at timestamptz NOT NULL DEFAULT now()` for timestamps.

## Examples
- `join_fish_transgene_alleles(fish_id, transgene_base_code, allele_number)`
- `join_fish_fluorescent_treatments(fish_id, ft_code)`
- `v_fluors_lu(code,label)`, `v_tags_lu(code,label)`, `v_dyes_lu(code,label)`
- `v_fish_overview_id` joins PK-based genotype + fluorescent rollups.

