-- =============================================================================
-- 🧩 CARP UUID ENTITY STANDARDIZATION MIGRATION
-- Consolidates all manual interactive steps performed during 2025-10-26 session
-- =============================================================================
begin;

-- 1️⃣ FISH → rename id → fish_uuid
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish' and column_name='id'
  ) then
    alter table public.fish rename column id to fish_uuid;
  end if;
end$$;

alter table public.fish
  alter column fish_uuid set default gen_random_uuid();

do $$
begin
  if not exists (
    select 1 from information_schema.table_constraints
    where table_schema='public' and table_name='fish' and constraint_type='PRIMARY KEY'
  ) then
    alter table public.fish add primary key (fish_uuid);
  end if;
end$$;

-- 2️⃣ TANKS → promote tank_uuid to PK
do $$
declare pk text;
begin
  select constraint_name into pk
  from information_schema.table_constraints
  where table_schema='public' and table_name='tanks' and constraint_type='PRIMARY KEY';
  if pk is not null then
    execute format('alter table public.tanks drop constraint %I cascade', pk);
  end if;
end$$;

alter table public.tanks add primary key (tank_uuid);

-- 3️⃣ LINK TABLE → rebuild
drop table if exists public.fish_tank_memberships cascade;
create table public.fish_tank_memberships (
  link_uuid uuid primary key default gen_random_uuid(),
  fish_uuid uuid not null references public.fish(fish_uuid) on delete cascade,
  tank_uuid uuid not null references public.tanks(tank_uuid) on delete cascade,
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create unique index uq_tank_active
  on public.fish_tank_memberships(tank_uuid)
  where ended_at is null;
create unique index uq_fish_tank_started
  on public.fish_tank_memberships(fish_uuid, tank_uuid, started_at);

-- 4️⃣ trigger
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger trg_fish_tank_memberships_updated_at
before update on public.fish_tank_memberships
for each row
execute function public.set_updated_at();

-- 5️⃣ dependent tank_status_history normalization
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='tank_status_history' and column_name='tank_uuid'
  ) then
    alter table public.tank_status_history add column tank_uuid uuid;
    update public.tank_status_history h
    set tank_uuid = t.tank_uuid
    from public.tanks t
    where h.tank_id = t.tank_id and h.tank_uuid is null;
    alter table public.tank_status_history drop column if exists tank_id;
  end if;
end$$;

-- 6️⃣ UUID-based view
create or replace view public.v_fish_current_tank_counts as
select f.fish_uuid,
       count(t.tank_uuid)::int as current_tanks
from public.fish f
left join public.fish_tank_memberships m
  on m.fish_uuid = f.fish_uuid and m.ended_at is null
left join public.tanks t
  on t.tank_uuid = m.tank_uuid
where coalesce(t.status,'active') in ('active','living')
group by f.fish_uuid;

commit;
