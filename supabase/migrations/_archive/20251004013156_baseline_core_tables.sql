begin;

create extension if not exists pgcrypto;

-- fish (cohort);
DO $$
begin
  if to_regclass('public.fish') is null then
    create table public.fish(
      id uuid primary key default gen_random_uuid(),
      fish_code text unique,
      name text,
      created_at timestamptz not null default now(),
      created_by text,
      date_birth date
    );
  end if;
end$$;

-- base allele pairs
do $$
begin
  if to_regclass('public.transgene_alleles') is null then
    create table public.transgene_alleles(
      transgene_base_code text not null,
      allele_number int not null,
      primary key (transgene_base_code, allele_number)
    );
  end if;
end$$;

-- fish ↔ allele link (nickname optional);
DO $$
begin
  if to_regclass('public.fish_transgene_alleles') is null then
    create table public.fish_transgene_alleles(
      fish_id uuid not null references public.fish(id) on delete cascade,
      transgene_base_code text not null,
      allele_number int not null,
      zygosity text,
      allele_nickname text,
      primary key (fish_id, transgene_base_code, allele_number),
      foreign key (transgene_base_code, allele_number)
        references public.transgene_alleles (transgene_base_code, allele_number)
        on delete cascade
    );
  end if;
end$$;

-- nickname registry (modern columns);
DO $$
begin
  if to_regclass('public.transgene_allele_registry') is null then
    create table public.transgene_allele_registry(
      id uuid primary key default gen_random_uuid(),
      transgene_base_code text not null,
      allele_number int not null,
      allele_nickname text not null,
      created_at timestamptz not null default now(),
      created_by text
    );
  end if;

  -- uniqueness (safe if already present)
  if not exists (select 1 from pg_class where relname='uq_tar_base_number' and relkind='i') then
    create unique index uq_tar_base_number
      on public.transgene_allele_registry (transgene_base_code, allele_number);
  end if;
  if not exists (select 1 from pg_class where relname='uq_tar_base_nickname' and relkind='i') then
    create unique index uq_tar_base_nickname
      on public.transgene_allele_registry (transgene_base_code, allele_nickname);
  end if;
end$$;

-- per-base counters
do $$
begin
  if to_regclass('public.transgene_allele_counters') is null then
    create table public.transgene_allele_counters(
      transgene_base_code text primary key,
      next_number int not null default 1
    );
  end if;
end$$;

commit;
