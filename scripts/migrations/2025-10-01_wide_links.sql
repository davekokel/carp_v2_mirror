-- scripts/migrations/2025-10-01_wide_links.sql

-- plasmids
create table if not exists public.plasmids (
  code text primary key,
  name text
);

create table if not exists public.fish_plasmids(
  fish_id uuid references public.fish(id) on delete cascade,
  plasmid_code text references public.plasmids(code) on delete restrict,
  primary key (fish_id, plasmid_code)
);

-- rnas
create table if not exists public.rnas (
  code text primary key,
  name text
);

create table if not exists public.fish_rnas(
  fish_id uuid references public.fish(id) on delete cascade,
  rna_code text references public.rnas(code) on delete restrict,
  primary key (fish_id, rna_code)
);

-- dyes
create table if not exists public.dyes (
  name text primary key
);

create table if not exists public.fish_dyes(
  fish_id uuid references public.fish(id) on delete cascade,
  dye_name text references public.dyes(name) on delete restrict,
  primary key (fish_id, dye_name)
);

-- fluors
create table if not exists public.fluors (
  name text primary key
);

create table if not exists public.fish_fluors(
  fish_id uuid references public.fluors(name) on delete restrict,
  fluor_name text references public.fluors(name) on delete restrict,
  primary key (fish_id, fluor_name)
);