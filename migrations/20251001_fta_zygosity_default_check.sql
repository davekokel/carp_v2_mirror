-- 20251001_fta_zygosity_default_check.sql
-- Make zygosity default to 'unknown' and enforce allowed values

begin;

-- Column default (safe if already set)
alter table public.fish_transgene_alleles
  alter column zygosity set default 'unknown';

-- Backfill existing blanks/nulls
update public.fish_transgene_alleles
set zygosity = 'unknown'
where zygosity is null or btrim(zygosity) = '';

-- Re-create the CHECK constraint (idempotent)
do $$
begin
  if exists (
    select 1 from pg_constraint
    where conname = 'fta_zygosity_check'
      and conrelid = 'public.fish_transgene_alleles'::regclass
  ) then
    execute 'alter table public.fish_transgene_alleles drop constraint fta_zygosity_check';
  end if;
  execute $sql$
    alter table public.fish_transgene_alleles
      add constraint fta_zygosity_check
      check (zygosity in ('heterozygous','homozygous','unknown'))
  $sql$;
end$$;

commit;
