begin;
create extension if not exists pgcrypto;
alter table public.fish add column if not exists id_uuid uuid default gen_random_uuid();
update public.fish set id_uuid = gen_random_uuid() where id_uuid is null;
create unique index if not exists uq_fish_id_uuid on public.fish(id_uuid);
commit;
