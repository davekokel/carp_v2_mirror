-- Ensure extensions
create extension if not exists pgcrypto;

-- fish: ensure id_uuid PK, fish_code, created_by
do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='fish' and column_name='id_uuid') then
    execute 'alter table public.fish add column id_uuid uuid not null default gen_random_uuid()';
    execute 'alter table public.fish add primary key (id_uuid)';
  end if;
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='fish' and column_name='fish_code') then
    execute 'alter table public.fish add column fish_code text';
  end if;
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='fish' and column_name='created_by') then
    execute 'alter table public.fish add column created_by text';
  end if;
end$$;

-- treatments: ensure id_uuid, treatment_type
do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='treatments' and column_name='id_uuid') then
    execute 'alter table public.treatments add column id_uuid uuid not null default gen_random_uuid()';
  end if;
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='treatments' and column_name='treatment_type') then
    execute 'alter table public.treatments add column treatment_type text not null default ''UNSPECIFIED''';
  end if;
end$$;

-- ensure unique id_uuid on treatments (ok if it’s already PK)
create unique index if not exists treatments_id_uuid_key on public.treatments (id_uuid);

-- fish_treatments table compatible with UI (drops+recreates locally)
drop table if exists public.fish_treatments cascade;
create table public.fish_treatments (
    id_uuid uuid not null default gen_random_uuid() primary key,
    fish_id uuid not null references public.fish (id_uuid) on delete cascade,
    treatment_id uuid not null references public.treatments (id_uuid),
    applied_at timestamptz,
    created_at timestamptz not null default now(),
    created_by text
);

-- summary view
drop view if exists public.v_fish_treatment_summary;
create view public.v_fish_treatment_summary as
select
    ft.fish_id,
    f.fish_code,
    t.treatment_type::text as treatment_type,
    t.treatment_type::text as treatment_name,
    null::treatment_route as route,
    ft.applied_at as started_at,
    null::timestamptz as ended_at,
    null::numeric as dose,
    null::text as vehicle
from public.fish_treatments as ft
inner join public.fish as f on ft.fish_id = f.id_uuid
inner join public.treatments as t on ft.treatment_id = t.id_uuid;
