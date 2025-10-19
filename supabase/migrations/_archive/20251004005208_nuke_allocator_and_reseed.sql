begin;

-- Drop registry and allocator state
drop table if exists public.transgene_allele_registry cascade;
drop table if exists public.transgene_allele_counters cascade;
drop table if exists public.transgene_alleles cascade;
drop table if exists public.fish_transgene_alleles cascade;

-- Recreate clean allocator tables
create table public.transgene_allele_registry (
    id uuid primary key default gen_random_uuid(),
    transgene_base_code text not null,
    allele_number integer not null,
    allele_nickname text not null,
    created_at timestamptz not null default now(),
    created_by text null
);
create unique index uq_tar_base_number
on public.transgene_allele_registry (transgene_base_code, allele_number);
create unique index uq_tar_base_nickname
on public.transgene_allele_registry (transgene_base_code, allele_nickname);

create table public.transgene_allele_counters (
    transgene_base_code text primary key,
    next_number integer not null default 1
);

-- Base allele pairs
create table public.transgene_alleles (
    transgene_base_code text not null,
    allele_number int not null,
    primary key (transgene_base_code, allele_number)
);

-- Fish↔allele link
create table public.fish_transgene_alleles (
    fish_id uuid not null references public.fish (id) on delete cascade,
    transgene_base_code text not null,
    allele_number int not null,
    zygosity text,
    allele_nickname text,
    primary key (fish_id, transgene_base_code, allele_number),
    foreign key (transgene_base_code, allele_number)
    references public.transgene_alleles (transgene_base_code, allele_number)
    on delete cascade
);

commit;
