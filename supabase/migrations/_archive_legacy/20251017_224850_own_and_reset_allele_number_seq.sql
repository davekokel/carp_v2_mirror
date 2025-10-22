-- Tie the sequence to the column so TRUNCATE ... RESTART IDENTITY resets it
-- and add a helper to sync it to the current table contents.

-- 1) Make sure the sequence exists
create sequence if not exists public.transgene_allele_number_seq;

-- 2) Own the sequence by the allele_number column (safe if already owned)
do $$
begin
  perform 1
  from information_schema.columns  where table_schema='public' and table_name='transgene_alleles' and column_name='allele_number';

  -- If the column exists, set ownership (no-op if already set)
  execute 'alter sequence public.transgene_allele_number_seq owned by public.transgene_alleles.allele_number';
exception
  when undefined_table then null;   -- tolerate environments not yet having the table
  when undefined_column then null;
end$$;

comment on sequence public.transgene_allele_number_seq is
'Global allele_number sequence; owned by transgene_alleles.allele_number so RESTART IDENTITY resets it.';

-- 3) Helper to sync sequence to current max(allele_number)
create or replace function public.reset_allele_number_seq() returns void
language sql as $$
  select setval('public.transgene_allele_number_seq',
                coalesce(max(allele_number),0), true)
  from public.transgene_alleles;
$$;

comment on function public.reset_allele_number_seq() is
'Sets allele_number sequence to max(allele_number) (or 0 if empty), so nextval() yields max+1.';
