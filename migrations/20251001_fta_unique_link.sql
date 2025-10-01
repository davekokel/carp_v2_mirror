-- 20251001_fta_unique_link.sql
-- Ensure each (fish_id, transgene_base_code, allele_number) appears once

begin;

-- Normalize blanks to NULL
update public.fish_transgene_alleles
set allele_number = null
where allele_number is not null and btrim(allele_number) = '';

-- Create a unique index treating NULL and '' consistently
create unique index if not exists uniq_fish_allele_link
  on public.fish_transgene_alleles (fish_id, transgene_base_code, coalesce(allele_number, ''))
  include (zygosity);

commit;
