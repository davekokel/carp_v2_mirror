CREATE OR REPLACE FUNCTION public.ensure_clutch_for_cross_instance()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
declare has_created_by boolean;
begin
  select exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutch_instances' and column_name='created_by'
  ) into has_created_by;

  if exists (select 1 from public.clutch_instances where cross_instance_id = new.id) then
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
end $function$
;
