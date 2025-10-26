-- Normalize created_by to UUID on core write-path tables and tighten autotank trigger.
-- Idempotent: adds temp columns if needed; preserves valid UUIDs; nulls non-UUID legacy text.

create extension if not exists pgcrypto;

-- helper: test if text looks like a uuid
create or replace function public._is_uuid(txt text)
returns boolean language sql immutable as $$
  select txt ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
$$;

-- 1) public.fish.created_by -> uuid (nullable). Keep only valid UUIDs; else NULL.
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish' and column_name='created_by' and data_type <> 'uuid'
  ) then
    alter table public.fish add column if not exists created_by_uuid uuid;
    update public.fish
       set created_by_uuid = case when public._is_uuid(created_by) then created_by::uuid else null end
     where created_by_uuid is null;
    alter table public.fish drop column created_by;
    alter table public.fish rename column created_by_uuid to created_by;
  end if;
end $$;

-- 2) Ensure these tables have created_by as UUID (add if missing but do not force fill)
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='tanks' and column_name='created_by'
  ) then
    alter table public.tanks add column created_by uuid;
  end if;
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='tanks' and column_name='created_by' and data_type <> 'uuid'
  ) then
    alter table public.tanks alter column created_by type uuid using null;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish_tank_memberships' and column_name='created_by'
  ) then
    alter table public.fish_tank_memberships add column created_by uuid;
  end if;
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish_tank_memberships' and column_name='created_by' and data_type <> 'uuid'
  ) then
    alter table public.fish_tank_memberships alter column created_by type uuid using null;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='tank_status_history' and column_name='created_by'
  ) then
    alter table public.tank_status_history add column created_by uuid;
  end if;
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='tank_status_history' and column_name='created_by' and data_type <> 'uuid'
  ) then
    alter table public.tank_status_history alter column created_by type uuid using null;
  end if;
end $$;

-- 3) Tighten the autotank trigger: no string -> uuid casts or 'system' fallbacks.
create or replace function public.trg_fish_autotank()
returns trigger
language plpgsql
as $$
declare
  v_tank_id   uuid := gen_random_uuid();
  v_tank_code text;
begin
  v_tank_code := 'TANK-' || NEW.fish_code || '-#1';

  insert into public.tanks (tank_id, tank_code, rack, position, created_at, created_by)
  values (v_tank_id, v_tank_code, null, null, now(), NEW.created_by)
  on conflict do nothing;

  insert into public.tank_status_history (tank_id, status, reason, changed_at, created_by)
  values (v_tank_id, 'new_tank', 'auto-create on fish import', now(), NEW.created_by)
  on conflict do nothing;

  insert into public.fish_tank_memberships (id, container_id, fish_id, created_at, created_by)
  values (gen_random_uuid(), v_tank_id, NEW.id, now(), NEW.created_by)
  on conflict do nothing;

  return NEW;
end;
$$;

drop trigger if exists bi_fish_autotank on public.fish;
create trigger bi_fish_autotank
  after insert on public.fish
  for each row
  execute function public.trg_fish_autotank();
