alter table public.clutch_instances
  add constraint if not exists uq_clutch_cross_instance unique (cross_instance_id);

create or replace function public.ensure_clutch_for_cross_instance()
returns trigger
language plpgsql
as $$
begin
  insert into public.clutch_instances (cross_instance_id, date_birth, created_by)
  select new.id, coalesce(new.date, current_date), coalesce(new.created_by,'system')
  where not exists (select 1 from public.clutch_instances where cross_instance_id=new.id);
  return new;
end
$$;

drop trigger if exists trg_cross_instance_auto_clutch on public.cross_instances;

create trigger trg_cross_instance_auto_clutch
after insert on public.cross_instances
for each row
execute function public.ensure_clutch_for_cross_instance();

insert into public.clutch_instances (cross_instance_id, date_birth, created_by)
select ci.id, coalesce(ci.date, current_date), coalesce(ci.created_by,'system')
from public.cross_instances ci
left join public.clutch_instances cl on cl.cross_instance_id=ci.id
where cl.id is null;
