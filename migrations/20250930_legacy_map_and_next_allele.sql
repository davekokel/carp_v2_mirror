-- 1) Legacy map table (text allele_number to match existing schema)
create table if not exists public.transgene_allele_legacy_map (
  transgene_base_code text not null,
  legacy_label        text not null,
  allele_number       text not null,
  primary key (transgene_base_code, legacy_label)
);

-- 2) Next allele allocator: cast text->int safely
create or replace function public.next_allele_number(p_code text)
returns integer
language sql
as $$
  select coalesce(
           max(nullif(allele_number, '')::int),  -- cast only non-empty values
           0
         ) + 1
  from public.transgene_alleles
  where transgene_base_code = p_code
    and allele_number ~ '^\d+$'                  -- numeric-only rows
$$;
