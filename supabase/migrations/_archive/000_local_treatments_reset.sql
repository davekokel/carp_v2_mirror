create extension if not exists pgcrypto;

drop view if exists public.v_fish_treatment_summary cascade;
drop table if exists public.fish_treatments cascade;
drop table if exists public.treatments cascade;
drop table if exists public.fish cascade;
do $$ begin
  if exists (select 1 from pg_type where typname='treatment_route') then
    execute 'drop type treatment_route';
  end if;
end $$;

create type treatment_route as enum ('bath','injection','feed','other');

create table public.fish (
  id_uuid uuid primary key default gen_random_uuid(),
  fish_code text,
  created_at timestamptz not null default now(),
  created_by text
);

create table public.treatments (
  id_uuid uuid primary key default gen_random_uuid(),
  treatment_type text not null
);

create table public.fish_treatments (
  id_uuid uuid primary key default gen_random_uuid(),
  fish_id uuid not null references public.fish(id_uuid) on delete cascade,
  treatment_id uuid not null references public.treatments(id_uuid),
  applied_at timestamptz,
  created_at timestamptz not null default now(),
  created_by text
);

create view public.v_fish_treatment_summary as
select
  ft.fish_id,
  f.fish_code,
  t.treatment_type::text as treatment_type,
  t.treatment_type::text as treatment_name,
  null::treatment_route  as route,
  ft.applied_at          as started_at,
  null::timestamptz      as ended_at,
  null::numeric          as dose,
  null::text             as vehicle
from public.fish_treatments ft
join public.fish f on f.id_uuid = ft.fish_id
join public.treatments t on t.id_uuid = ft.treatment_id;
