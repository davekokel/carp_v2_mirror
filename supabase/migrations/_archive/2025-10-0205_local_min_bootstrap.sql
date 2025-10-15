create extension if not exists pgcrypto;

create table if not exists public.fish (
  id_uuid uuid not null default gen_random_uuid() primary key,
  fish_code text,
  created_at timestamptz not null default now(),
  created_by text
);
DO 28762
begin
  if not exists (select 1 from pg_type where typname = 'treatment_route') then
    create type treatment_route as enum ('bath','injection','feed','other');
  end if;
end$$;

create table if not exists public.treatments (
  id_uuid uuid not null default gen_random_uuid() primary key,
  treatment_type text not null
);

create table if not exists public.fish_treatments (
  id_uuid uuid not null default gen_random_uuid() primary key,
  fish_id uuid not null references public.fish(id_uuid) on delete cascade,
  treatment_id uuid not null references public.treatments(id_uuid),
  applied_at timestamptz,
  created_at timestamptz not null default now(),
  created_by text
);

drop view if exists public.v_fish_treatment_summary;
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
