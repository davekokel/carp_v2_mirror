alter table public.clutch_instances add column if not exists birthday date;
alter table public.clutch_instances add column if not exists created_by text;
alter table public.clutch_instances add constraint if not exists uq_clutch_cross_instance unique (cross_instance_id);

create or replace function public.ensure_clutch_for_cross_instance()
returns trigger
language plpgsql
as $$
declare has_created_by boolean;
begin
  select exists (
    select 1 from information_schema.columns  where table_schema='public' and table_name='clutch_instances' and column_name='created_by'
  ) into has_created_by;

  if exists (select 1 from public.clutch_instances  where cross_instance_id = new.id) then
    return new;
  end if;

  if has_created_by then
    insert into public.clutch_instances (cross_instance_id, birthday, created_by)
    values (new.id, coalesce(new.cross_date, current_date), coalesce(new.created_by, 'system'));
  else
    insert into public.clutch_instances (cross_instance_id, birthday)
    values (new.id, coalesce(new.cross_date, current_date));
  end if;

  return new;
end
$$;

drop trigger if exists trg_cross_instance_auto_clutch on public.cross_instances;

create trigger trg_cross_instance_auto_clutch
after insert on public.cross_instances
for each row
execute function public.ensure_clutch_for_cross_instance();

insert into public.clutch_instances (cross_instance_id, birthday, created_by)
select ci.id, coalesce(ci.cross_date, current_date), coalesce(ci.created_by, 'system')
from public.cross_instances AS ci
left join public.clutch_instances AS cl on cl.cross_instance_id = ci.id
where cl.cross_instance_id is null;
