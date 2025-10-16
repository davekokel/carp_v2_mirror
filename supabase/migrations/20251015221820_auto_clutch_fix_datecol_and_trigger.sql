-- 1) Enforce one-to-one
alter table public.clutch_instances
  add constraint if not exists uq_clutch_cross_instance unique (cross_instance_id);

-- 2) Trigger function that auto-detects the date column on clutch_instances
create or replace function public.ensure_clutch_for_cross_instance()
returns trigger
language plpgsql
as $$
declare
  has_birthday     boolean;
  has_date_birth   boolean;
  has_date_generic boolean;
  v_date date;
begin
  select exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutch_instances'
      and column_name='birthday'
  ) into has_birthday;

  select exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutch_instances'
      and column_name='date_birth'
  ) into has_date_birth;

  select exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutch_instances'
      and column_name='date'
  ) into has_date_generic;

  v_date := coalesce(new.date, current_date);

  -- nothing to do if it already exists
  if exists (select 1 from public.clutch_instances where cross_instance_id = new.id) then
    return new;
  end if;

  if has_birthday then
    insert into public.clutch_instances (cross_instance_id, birthday, created_by)
    values (new.id, v_date, coalesce(new.created_by,'system'));

  elsif has_date_birth then
    insert into public.clutch_instances (cross_instance_id, date_birth, created_by)
    values (new.id, v_date, coalesce(new.created_by,'system'));

  elsif has_date_generic then
    insert into public.clutch_instances (cross_instance_id, date, created_by)
    values (new.id, v_date, coalesce(new.created_by,'system'));

  else
    raise exception 'clutch_instances needs one of: birthday, date_birth, or date';
  end if;

  return new;
end
$$;

-- 3) Recreate trigger
drop trigger if exists trg_cross_instance_auto_clutch on public.cross_instances;
create trigger trg_cross_instance_auto_clutch
after insert on public.cross_instances
for each row
execute function public.ensure_clutch_for_cross_instance();

-- 4) Backfill any missing clutch_instances using the detected date column
do $$
declare
  has_birthday     boolean;
  has_date_birth   boolean;
  has_date_generic boolean;
begin
  select exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutch_instances' and column_name='birthday'
  ) into has_birthday;

  select exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutch_instances' and column_name='date_birth'
  ) into has_date_birth;

  select exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutch_instances' and column_name='date'
  ) into has_date_generic;

  if has_birthday then
    insert into public.clutch_instances (cross_instance_id, birthday, created_by)
    select ci.id, coalesce(ci.date, current_date), coalesce(ci.created_by,'system')
    from public.cross_instances ci
    left join public.clutch_instances cl on cl.cross_instance_id = ci.id
    where cl.id is null;
  elsif has_date_birth then
    insert into public.clutch_instances (cross_instance_id, date_birth, created_by)
    select ci.id, coalesce(ci.date, current_date), coalesce(ci.created_by,'system')
    from public.cross_instances ci
    left join public.clutch_instances cl on cl.cross_instance_id = ci.id
    where cl.id is null;
  elsif has_date_generic then
    insert into public.clutch_instances (cross_instance_id, date, created_by)
    select ci.id, coalesce(ci.date, current_date), coalesce(ci.created_by,'system')
    from public.cross_instances ci
    left join public.clutch_instances cl on cl.cross_instance_id = ci.id
    where cl.id is null;
  else
    raise exception 'clutch_instances needs one of: birthday, date_birth, or date';
  end if;
end $$;
