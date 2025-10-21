do $$
declare host text := inet_server_addr()::text;
begin
  if host not in ('127.0.0.1','::1') then
    raise exception 'Refusing to reset: %', host;
  end if;
end$$;

begin;

drop schema if exists public cascade;
create schema public;

create extension if not exists pgcrypto;

create table public.containers (
  id             uuid primary key default gen_random_uuid(),
  label          text,
  container_type text not null default 'inventory_tank',
  status         text not null default 'new_tank',
  tank_volume_l  numeric,
  fish_code      text,
  tank_code      text,
  note           text,
  created_by     text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz
);

create index if not exists containers_status_idx on public.containers (status);
create index if not exists containers_type_idx   on public.containers (container_type);
create index if not exists containers_created_ix on public.containers (created_at desc);

create or replace view public.v_tanks as
select
  c.id                          as tank_id,
  coalesce(c.label,'')          as label,
  coalesce(c.tank_code,'')      as tank_code,
  coalesce(c.fish_code,'')      as fish_code,
  coalesce(c.status,'new_tank') as status,
  c.tank_volume_l               as capacity,
  c.created_at                  as tank_created_at,
  c.updated_at                  as tank_updated_at
from public.containers c;

commit;
