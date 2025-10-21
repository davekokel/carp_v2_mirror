alter table public.fish add column if not exists id_uuid uuid generated always as (id) stored;
