begin;

-- Ensure fish has id_uuid mirror (safe even if already present)
alter table public.fish
  add column if not exists id_uuid uuid generated always as (id) stored;

-- Minimal mapping table if seeds are referenced downstream
create table if not exists public.fish_seed_batches(
  fish_id uuid primary key references public.fish(id) on delete cascade,
  seed_batch_id text
);

-- Optional: an empty seed_batches *view* to satisfy stray joins without multiplying rows.
-- We expose zero rows and a batch_label column; any LEFT JOINs just see NULL.
drop view if exists public.seed_batches cascade;
create view public.seed_batches as
select null::text as batch_label
where false;

commit;
