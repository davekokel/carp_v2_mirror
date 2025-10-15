begin;

-- 1) truncate treatments if present
do $$
begin
  if to_regclass('public.injected_plasmid_treatments') is not null then
    truncate table public.injected_plasmid_treatments restart identity;
  end if;
  if to_regclass('public.injected_rna_treatments') is not null then
    truncate table public.injected_rna_treatments restart identity;
  end if;
end$$;

-- 2) truncate links & fish (guarded);
DO $$
begin
  if to_regclass('public.fish_transgene_alleles') is not null then
    truncate table public.fish_transgene_alleles restart identity;
  end if;
  if to_regclass('public.fish') is not null then
    truncate table public.fish restart identity cascade;
  end if;
end$$;

-- 3) truncate allocator registry & per-base counters (guarded);
DO $$
begin
  if to_regclass('public.transgene_allele_registry') is not null then
    truncate table public.transgene_allele_registry restart identity;
  end if;
  if to_regclass('public.transgene_allele_counters') is not null then
    truncate table public.transgene_allele_counters restart identity;
  end if;
end$$;

-- 4) recreate allocator tables if missing (idempotent);
DO $$
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
  end if;

  if not exists (select 1 from pg_class where relname='uq_tar_base_number' and relkind='i') then
    create unique index uq_tar_base_number
      on public.transgene_allele_registry (transgene_base_code, allele_number);
  end if;
  if not exists (select 1 from pg_class where relname='uq_tar_base_nickname' and relkind='i') then
    create unique index uq_tar_base_nickname
      on public.transgene_allele_registry (transgene_base_code, allele_nickname);
  end if;

  if to_regclass('public.transgene_allele_counters') is null then
    create table public.transgene_allele_counters(
      transgene_base_code text primary key,
      next_number integer not null default 1
    );
  end if;
end$$;

commit;
