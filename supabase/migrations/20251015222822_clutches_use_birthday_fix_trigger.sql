-- Ensure schema uses `birthday` (already present from prior migration)
alter table public.clutch_instances
  add column if not exists birthday date;

-- One-to-one guard
alter table public.clutch_instances
  add constraint if not exists uq_clutch_cross_instance
  unique (cross_instance_id);

-- Correct trigger function: write to `birthday` from cross_instances.cross_date
create or replace function public.ensure_clutch_for_cross_instance()
returns trigger
language plpgsql as $$
begin
  if exists (select 1 from public.clutch_instances where cross_instance_id = new.id) then
    return new;
  end if;

  insert into public.clutch_instances (cross_instance_id, birthday, created_by)
  values (new.id, coalesce(new.cross_date, current_date), coalesce(new.created_by, 'system'));

  return new;
end
$$;

-- Reinstall trigger idempotently
drop trigger if exists trg_cross_instance_auto_clutch on public.cross_instances;
create trigger trg_cross_instance_auto_clutch
after insert on public.cross_instances
for each row
execute function public.ensure_clutch_for_cross_instance();

-- Backfill missing rows and missing birthdays
insert into public.clutch_instances (cross_instance_id, birthday, created_by)
select ci.id, coalesce(ci.cross_date, current_date), coalesce(ci.created_by,'system')
from public.cross_instances ci
left join public.clutch_instances cl on cl.cross_instance_id = ci.id
where cl.cross_instance_id is null;

update public.clutch_instances cl
set birthday = coalesce(cl.birthday, ci.cross_date)
from public.cross_instances ci
where cl.cross_instance_id = ci.id
  and cl.birthday is null;
