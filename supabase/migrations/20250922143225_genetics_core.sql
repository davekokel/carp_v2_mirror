-- Transgenes (already present in your DB, but keep this idempotent)
create table if not exists public.transgenes (
  transgene_base_code text primary key
);

-- Specific alleles of a transgene (composite PK)
create table if not exists public.transgene_alleles (
  transgene_base_code text not null,
  allele_number       text not null,
  description         text,
  constraint transgene_alleles_pk primary key (transgene_base_code, allele_number),
  constraint transgene_alleles_fk_transgene
    foreign key (transgene_base_code)
    references public.transgenes(transgene_base_code)
    on delete cascade
);

-- Link: fish ↔ specific allele (+ optional zygosity)
create table if not exists public.fish_transgene_alleles (
  fish_id             uuid not null,
  transgene_base_code text not null,
  allele_number       text not null,
  zygosity            text,  -- e.g. homozygous / heterozygous / unknown
  constraint fish_transgene_alleles_pk
    primary key (fish_id, transgene_base_code, allele_number),
  constraint fish_transgene_alleles_fk_fish
    foreign key (fish_id) references public.fish(id)
    on delete cascade,
  constraint fish_transgene_alleles_fk_allele
    foreign key (transgene_base_code, allele_number)
    references public.transgene_alleles(transgene_base_code, allele_number)
    on delete cascade
);

-- Optional nudge away from legacy booleans
do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema='public' and table_name='fish'
      and column_name like 'has_%'
  ) then
    raise notice 'Consider removing legacy has_* columns on public.fish (use fish_transgene_alleles instead).';
  end if;
end$$;
