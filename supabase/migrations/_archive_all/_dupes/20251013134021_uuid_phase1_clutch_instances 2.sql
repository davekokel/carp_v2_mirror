begin;
create extension if not exists pgcrypto;
alter table public.clutch_instances add column if not exists id_uuid uuid default gen_random_uuid();
update public.clutch_instances set id_uuid = gen_random_uuid() where id_uuid is null;
create unique index if not exists uq_clutch_instances_id_uuid on public.clutch_instances(id_uuid);
commit;
