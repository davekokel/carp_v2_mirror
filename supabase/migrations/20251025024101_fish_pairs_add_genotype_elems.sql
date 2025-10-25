begin;

-- Add snapshot column for conceptual pair genotype tokens
alter table public.fish_pairs
  add column if not exists genotype_elems text[];

-- Optional: enable fast search by elements (keep commented if not needed yet)
-- create index if not exists ix_fish_pairs_genotype_elems
--   on public.fish_pairs using gin (genotype_elems);

commit;
