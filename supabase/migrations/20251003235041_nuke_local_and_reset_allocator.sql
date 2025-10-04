begin;

-- 0) Confirm we are on a local DB (optional but wise)
-- select current_database(), inet_server_addr()::text, inet_server_port()::int;

-- 1) Truncate treatments if present
do $$
begin
  if to_regclass('public.injected_plasmid_treatments') is not null then
    truncate table public.injected_plasmid_treatments restart identity;
  end if;
  if to_regclass('public.injected_rna_treatments') is not null then
    truncate table public.injected_rna_treatments restart identity;
  end if;
end$$;

-- 2) Truncate links & fish (CASCADE handles children if any)
-- Do links explicitly first to be crystal-clear
if exists (select 1 from pg_class where relname='fish_transgene_alleles') then
  truncate table public.fish_transgene_alleles restart identity;
end if;

if exists (select 1 from pg_class where relname='fish') then
  truncate table public.fish restart identity cascade;
end if;

-- 3) Truncate allocator registry & per-base counters
do $$
begin
  if to_regclass('public.transgene_allele_registry') is not null then
    truncate table public.transgene_allele_registry restart identity;
  end if;
  if to_regclass('public.transgene_allele_counters') is not null then
    truncate table public.transgene_allele_counters restart identity;
  end if;
end$$;

-- 4) (Optional) sanity: ensure the allocator tables still exist
do $$
begin
  if to_regclass('public.transgene_allele_registry') is null then
    create table public.transgene_allele_registry(
      id uuid primary key default gen_random_uuid(),
      transgene_base_code text not null,
      allele_number integer not null,
      allele_nickname text not null,
      created_at timestamptz not null default now(),
      created_by text null
    );
    create unique index if not exists uq_tar_base_number
      on public.transgene_allele_registry (transgene_base_code, allele_number);
    create unique index if not exists uq_tar_base_nickname
      on public.transgene_allele_registry (transgene_base_code, allele_nickname);
  end if;

  if to_regclass('public.transgene_allele_counters') is null then
    create table public.transgene_allele_counters (
      transgene_base_code text primary key,
      next_number integer not null default 1
    );
  end if;
end$$;

commit;
