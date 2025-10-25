begin;

create extension if not exists pgcrypto;

-- Core fish table
create table if not exists public.fish (
  id                  uuid primary key default gen_random_uuid(),
  fish_code           text unique not null,
  name                text,
  nickname            text,
  genetic_background  text,
  genotype            text,
  date_birth          date,
  created_by          text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz
);

-- Optional allele mapping (pages join this)
create table if not exists public.fish_transgene_alleles (
  fish_id              uuid references public.fish(id) on delete cascade,
  transgene_base_code  text,
  allele_number        int,
  allele_name          text,
  allele_nickname      text,
  primary key (fish_id, transgene_base_code, allele_number)
);

-- Allele registry for pretty labels
create table if not exists public.transgene_alleles (
  transgene_base_code  text,
  allele_number        int,
  allele_name          text,
  allele_nickname      text,
  primary key (transgene_base_code, allele_number)
);

-- Canonical light view used by the UI
create or replace view public.v_fish as
select
  f.id,
  f.fish_code,
  coalesce(f.name,'')       as name,
  coalesce(f.nickname,'')   as nickname,
  f.date_birth,
  coalesce(f.genetic_background,'') as genetic_background,
  coalesce(f.genotype,'')   as genotype,
  f.created_at,
  f.updated_at
from public.fish f;

commit;
