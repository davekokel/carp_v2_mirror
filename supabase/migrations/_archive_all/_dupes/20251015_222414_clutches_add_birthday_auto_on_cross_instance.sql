-- 1) Ensure a date column for clutches
alter table public.clutch_instances
  add column if not exists birthday date;

-- 2) One-to-one: each cross_instance has at most one clutch_instance
alter table public.clutch_instances
  add constraint if not exists uq_clutch_cross_instance
  unique (cross_instance_id);

-- 3) Trigger function: create clutch_instance when a cross_instance is inserted
create or replace function public.ensure_clutch_for_cross_instance()
returns trigger
language plpgsql
as $$
begin
  -- do nothing if it already exists
  if exists (select 1 from public.clutch_instances  where cross_instance_id = new.id) then
    return new;
  end if;

  insert into public.clutch_instances (cross_instance_id, birthday, created_by)
  values (new.id, coalesce(new.cross_date, current_date), coalesce(new.created_by, 'system'));

  return new;
end
$$;

-- 4) Recreate trigger idempotently
drop trigger if exists trg_cross_instance_auto_clutch on public.cross_instances;
create trigger trg_cross_instance_auto_clutch
after insert on public.cross_instances
for each row
execute function public.ensure_clutch_for_cross_instance();

-- 5) Backfill birthday for any existing clutch rows missing it
update public.clutch_instances cl
set birthday = coalesce(cl.birthday, ci.cross_date)
from public.cross_instances AS ci
where cl.cross_instance_id = ci.id
  and cl.birthday is null;

-- 6) Backfill missing clutch rows for existing cross_instances
insert into public.clutch_instances (cross_instance_id, birthday, created_by)
select ci.id, coalesce(ci.cross_date, current_date), coalesce(ci.created_by, 'system')
from public.cross_instances AS ci
left join public.clutch_instances AS cl on cl.cross_instance_id = ci.id
where cl.cross_instance_id is null;
