#!/usr/bin/env bash
set -euo pipefail

CSV_DIR="${1:-}"
DB_URL="${2:-${LOCAL_DB_URL:-}}"

if [[ -z "$CSV_DIR" || -z "$DB_URL" ]]; then
  echo "Usage: $0 /path/to/core_seedkit [DB_URL]"
  echo "  (or set LOCAL_DB_URL in your env)"
  exit 1
fi
if [[ ! -d "$CSV_DIR" ]]; then
  echo "❌ Folder not found: $CSV_DIR"
  exit 1
fi

# Required files
need=(transgenes.csv transgene_alleles.csv fish.csv fish_transgene_alleles.csv)
for f in "${need[@]}"; do
  [[ -f "$CSV_DIR/$f" ]] || { echo "❌ Missing $f in $CSV_DIR"; exit 1; }
done

echo "→ Loading clean seedkit from: $CSV_DIR"
echo "→ DB: ${DB_URL%%@*}@…"

psql "$DB_URL" -v ON_ERROR_STOP=1 -v CSV_DIR="$CSV_DIR" <<SQL
BEGIN;

-- temp tables shaped to CSVs
create temp table _tg       (transgene_base_code text, name text, description text) on commit drop;
create temp table _allele   (transgene_base_code text, allele_number text, description text) on commit drop;
create temp table _fish     (fish_code text, name text, date_of_birth date, status text, strain text) on commit drop;
create temp table _links    (fish_code text, transgene_base_code text, allele_number text) on commit drop;

\copy _tg     from :'CSV_DIR'/transgenes.csv                 with (format csv, header true)
\copy _allele from :'CSV_DIR'/transgene_alleles.csv          with (format csv, header true)
\copy _fish   from :'CSV_DIR'/fish.csv                       with (format csv, header true)
\copy _links  from :'CSV_DIR'/fish_transgene_alleles.csv     with (format csv, header true)

-- 1) upsert transgenes
insert into public.transgenes (transgene_base_code, name, description)
select lower(trim(transgene_base_code)), nullif(trim(name),''), nullif(trim(description),'')
from _tg
where coalesce(trim(transgene_base_code),'') <> ''
on conflict (transgene_base_code) do update
  set name = coalesce(excluded.name, public.transgenes.name),
      description = coalesce(excluded.description, public.transgenes.description);

-- 2) upsert alleles
insert into public.transgene_alleles (transgene_base_code, allele_number, description)
select lower(trim(transgene_base_code)), lower(trim(allele_number)), nullif(trim(description),'')
from _allele
where coalesce(trim(transgene_base_code),'') <> '' and coalesce(trim(allele_number),'') <> ''
on conflict (transgene_base_code, allele_number) do update
  set description = coalesce(excluded.description, public.transgene_alleles.description);

-- 3) upsert fish (identified by fish_code)
insert into public.fish (name, date_of_birth, status, strain)
select lower(trim(fish_code)),
       nullif(trim(name),''),
       nullif(trim(date_of_birth),'')::date,
       nullif(trim(status),''),
       nullif(trim(strain),'')
from _fish
where coalesce(trim(fish_code),'') <> ''
on conflict (fish_code) do update
  set name = coalesce(excluded.name, public.fish.name),
      date_of_birth = coalesce(excluded.date_of_birth, public.fish.date_of_birth),
      status = coalesce(excluded.status, public.fish.status),
      strain = coalesce(excluded.strain, public.fish.strain);

-- 4) link fish → allele (resolve fish_id, enforce FK)
insert into public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
select f.id,
       lower(trim(l.transgene_base_code)),
       lower(trim(l.allele_number))
from _links l
join public.fish f
  on lower(trim(f.fish_code)) = lower(trim(l.fish_code))
join public.transgene_alleles a
  on a.transgene_base_code = lower(trim(l.transgene_base_code))
 and a.allele_number       = lower(trim(l.allele_number))
where coalesce(trim(l.fish_code),'') <> ''
  and coalesce(trim(l.transgene_base_code),'') <> ''
  and coalesce(trim(l.allele_number),'') <> ''
on conflict (fish_id, transgene_base_code, allele_number) do nothing;

COMMIT;

-- quick summary
\\echo
\\echo == summary ==
select 'transgenes'                as table, count(*) from public.transgenes
union all select 'transgene_alleles', count(*) from public.transgene_alleles
union all select 'fish',              count(*) from public.fish
union all select 'fish_transgene_alleles', count(*) from public.fish_transgene_alleles
order by 1;
SQL
