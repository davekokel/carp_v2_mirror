#!/usr/bin/env bash
set -euo pipefail

CSV_DIR="${1:-}"
DB_URL="${2:-${LOCAL_DB_URL:-}}"

if [[ -z "${CSV_DIR}" || -z "${DB_URL}" ]]; then
  echo "Usage: $0 /absolute/path/to/core_seedkit_folder [DB_URL]"
  exit 1
fi
if [[ ! -d "$CSV_DIR" ]]; then
  echo "❌ Folder not found: $CSV_DIR"
  exit 1
fi

echo "→ Loading clean seedkit from: $CSV_DIR"
echo "→ DB: ${DB_URL%%@*}@…"

# Make absolute paths (shell expands here)
FISH_CSV="$CSV_DIR/fish.csv"
TRANSGENES_CSV="$CSV_DIR/transgenes.csv"
TRANSGENE_ALLELES_CSV="$CSV_DIR/transgene_alleles.csv"
FISH_TG_ALLELES_CSV="$CSV_DIR/fish_transgene_alleles.csv"

# Build a temp SQL with literal paths (no psql variables involved)
TMP_SQL="$(mktemp -t load_core_seedkit.XXXXXX.sql)"
cat > "$TMP_SQL" <<SQL
BEGIN;

-- staging tables (drop/create so re-runs are clean)
drop table if exists raw.core_fish_csv                      cascade;
drop table if exists raw.core_transgenes_csv                cascade;
drop table if exists raw.core_transgene_alleles_csv         cascade;
drop table if exists raw.core_fish_transgene_alleles_csv    cascade;

create table raw.core_fish_csv (
  fish_code text,
  name text,
  date_of_birth date,
  strain text,
  status text
);

create table raw.core_transgenes_csv (
  transgene_base_code text,
  description text
);

create table raw.core_transgene_alleles_csv (
  transgene_base_code text,
  allele_number text,
  description text
);

create table raw.core_fish_transgene_alleles_csv (
  fish_code text,
  transgene_base_code text,
  allele_number text,
  zygosity text
);

\\copy raw.core_fish_csv                      from '$FISH_CSV'                      with (format csv, header true)
\\copy raw.core_transgenes_csv                from '$TRANSGENES_CSV'                with (format csv, header true)
\\copy raw.core_transgene_alleles_csv         from '$TRANSGENE_ALLELES_CSV'         with (format csv, header true)
\\copy raw.core_fish_transgene_alleles_csv    from '$FISH_TG_ALLELES_CSV'           with (format csv, header true)

-- upsert core tables
insert into public.transgenes (transgene_base_code, description)
select lower(trim(transgene_base_code)), nullif(trim(description),'')
from raw.core_transgenes_csv
where coalesce(trim(transgene_base_code),'') <> ''
on conflict (transgene_base_code) do update
  set description = coalesce(excluded.description, public.transgenes.description);

insert into public.transgene_alleles (transgene_base_code, allele_number, description)
select lower(trim(transgene_base_code)), lower(trim(allele_number)), nullif(trim(description),'')
from raw.core_transgene_alleles_csv
where coalesce(trim(transgene_base_code),'') <> ''
  and coalesce(trim(allele_number),'') <> ''
on conflict (transgene_base_code, allele_number) do update
  set description = coalesce(excluded.description, public.transgene_alleles.description);

insert into public.fish (fish_code, name, date_of_birth, strain, status)
select lower(trim(fish_code)), nullif(trim(name),''), date_of_birth, nullif(trim(strain),''), nullif(trim(status),'')
from raw.core_fish_csv
where coalesce(trim(fish_code),'') <> ''
on conflict (fish_code) do update
  set name = coalesce(excluded.name, public.fish.name);

insert into public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
select f.id,
       l.transgene_base_code,
       l.allele_number
from (
  select lower(trim(fish_code)) as fish_code,
         lower(trim(transgene_base_code)) as transgene_base_code,
         lower(trim(allele_number)) as allele_number
  from raw.core_fish_transgene_alleles_csv
  where coalesce(trim(fish_code),'') <> ''
    and coalesce(trim(transgene_base_code),'') <> ''
    and coalesce(trim(allele_number),'') <> ''
) l
join public.fish f on f.fish_code = l.fish_code
join public.transgene_alleles a
  on a.transgene_base_code = l.transgene_base_code
 and a.allele_number       = l.allele_number
on conflict (fish_id, transgene_base_code, allele_number) do nothing;

COMMIT;

\\echo
\\echo == summary ==
select 'transgenes'                as table, count(*) from public.transgenes
union all select 'transgene_alleles', count(*) from public.transgene_alleles
union all select 'fish',              count(*) from public.fish
union all select 'fish_transgene_alleles', count(*) from public.fish_transgene_alleles
order by 1;
SQL

psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$TMP_SQL"
rm -f "$TMP_SQL"
