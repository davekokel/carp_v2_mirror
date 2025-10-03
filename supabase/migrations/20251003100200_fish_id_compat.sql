begin;
alter table public.fish add column if not exists id uuid generated always as (id_uuid) stored;
create unique index if not exists uq_fish_id_compat on public.fish(id);
commit;
