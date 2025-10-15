begin;

-- 1. Drop everything (safe if missing);
DO $$
declare
  rec record;
begin
  for rec in
    select table_name
    from information_schema.tables
    where table_schema='public' and table_type='BASE TABLE'
  loop
    execute format('drop table if exists public.%I cascade', rec.table_name);
  end loop;
end$$;

-- 2. Recreate allocator core
create table public.transgene_allele_registry (
  id uuid primary key default gen_random_uuid(),
  transgene_base_code text not null,
  allele_number int not null,
  allele_nickname text not null,
  created_at timestamptz not null default now(),
  created_by text null,
  unique (transgene_base_code, allele_number),
  unique (transgene_base_code, allele_nickname)
);

create table public.transgene_allele_counters (
  transgene_base_code text primary key,
  next_number int not null default 1
);

create table public.transgene_alleles (
  transgene_base_code text not null,
  allele_number int not null,
  primary key (transgene_base_code, allele_number)
);

commit;
