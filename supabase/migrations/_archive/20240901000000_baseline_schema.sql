begin;

create extension if not exists pgcrypto;

create table public.fish (
  id uuid primary key default gen_random_uuid(),
  fish_code text unique,
  name text,
  created_at timestamptz not null default now(),
  created_by text,
  date_birth date
);

alter table public.fish
  add column if not exists id_uuid uuid generated always as (id) stored;
create unique index if not exists uq_fish_id_uuid_compat on public.fish(id_uuid);

create table public.fish_transgene_alleles (
  fish_id uuid not null references public.fish(id) on delete cascade,
  transgene_base_code text not null,
  allele_number int not null,
  zygosity text,
  primary key (fish_id, transgene_base_code, allele_number)
);

create table public.plasmids (
  id uuid primary key default gen_random_uuid(),
  plasmid_code text unique,
  name text
);

create table public.injected_plasmid_treatments (
  id uuid primary key default gen_random_uuid(),
  fish_id uuid not null references public.fish(id) on delete cascade,
  plasmid_id uuid not null references public.plasmids(id) on delete restrict,
  amount numeric null,
  units text null,
  at_time timestamptz null,
  note text null,
  unique (fish_id, plasmid_id, at_time, amount, units, note)
);

create table public.rnas (
  id uuid primary key default gen_random_uuid(),
  rna_code text unique,
  name text
);

create table public.injected_rna_treatments (
  id uuid primary key default gen_random_uuid(),
  fish_id uuid not null references public.fish(id) on delete cascade,
  rna_id uuid not null references public.rnas(id) on delete restrict,
  amount numeric null,
  units text null,
  at_time timestamptz null,
  note text null,
  unique (fish_id, rna_id, at_time, amount, units, note)
);

create or replace view public.v_fish_overview as
select
  f.id,
  f.fish_code,
  f.name,
  (
    select array_to_string(array_agg(x.base), ', ')
    from (select distinct t.transgene_base_code as base
          from public.fish_transgene_alleles t
          where t.fish_id=f.id
          order by 1) x
  ) as transgene_base_code_filled,
  (
    select array_to_string(array_agg(x.an), ', ')
    from (select distinct (t.allele_number::text) as an
          from public.fish_transgene_alleles t
          where t.fish_id=f.id
          order by 1) x
  ) as allele_code_filled,
  null::text as allele_name_filled,
  f.created_at,
  f.created_by
from public.fish f;

commit;
