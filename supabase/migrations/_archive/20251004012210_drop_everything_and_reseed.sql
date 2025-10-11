begin;

-- Remove derived views first
drop view if exists public.vw_fish_overview_with_label cascade;
drop view if exists public.v_fish_overview cascade;

-- Truncate domain tables (cascades clear links)
do $$
begin
  if to_regclass('public.fish') is not null then
    execute 'truncate table public.fish restart identity cascade';
  end if;
  if to_regclass('public.transgene_allele_registry') is not null then
    execute 'truncate table public.transgene_allele_registry restart identity';
  end if;
  if to_regclass('public.transgene_allele_counters') is not null then
    execute 'truncate table public.transgene_allele_counters restart identity';
  end if;
  if to_regclass('public.transgene_alleles') is not null then
    execute 'truncate table public.transgene_alleles restart identity';
  end if;
end$$;

-- (Re)create allocator tables cleanly
create table if not exists public.transgene_allele_registry(
  id uuid primary key default gen_random_uuid(),
  transgene_base_code text not null,
  allele_number int not null,
  allele_nickname text not null,
  created_at timestamptz not null default now(),
  created_by text null,
  unique (transgene_base_code, allele_number),
  unique (transgene_base_code, allele_nickname)
);

create table if not exists public.transgene_allele_counters(
  transgene_base_code text primary key,
  next_number int not null default 1
);

create table if not exists public.transgene_alleles(
  transgene_base_code text not null,
  allele_number int not null,
  primary key (transgene_base_code, allele_number)
);

commit;
