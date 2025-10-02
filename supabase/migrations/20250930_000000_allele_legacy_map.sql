-- Create the legacy label mapping table (safe to rerun)
create table if not exists public.transgene_allele_legacy_map (
  transgene_base_code text not null,
  legacy_label        text not null,
  allele_number       text not null,
  created_at          timestamptz default now(),
  primary key (transgene_base_code, legacy_label)
);

-- Helpful index for transgene_alleles (safe to add if missing)
create index if not exists idx_transgene_alleles_code_num
  on public.transgene_alleles (transgene_base_code, allele_number);

-- Next allele number helper: returns text; only looks at digit-only alleles
create or replace function public.next_allele_number(code text)
returns text
language sql
stable
as $$
with digits as (
  select max((allele_number)::int) as maxn
  from public.transgene_alleles
  where transgene_base_code = code
    and allele_number ~ '^[0-9]+$'
)
select coalesce((select (maxn+1)::text from digits), '1');
$$;
