CREATE OR REPLACE FUNCTION public.trg_cp_require_planned_crosses()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
declare
  v_has int;
begin
  if (TG_OP = 'UPDATE') and (OLD.status = 'draft') and (NEW.status <> 'draft') then
    select count(*) into v_has
    from public.planned_crosses pc
    where pc.clutch_id = NEW.id
      and pc.cross_id is not null;
    if coalesce(v_has,0) = 0 then
      raise exception 'Cannot set status %: no planned_crosses with cross_id for clutch_plan %',
        NEW.status, NEW.clutch_code
        using errcode = '23514';
    end if;
  end if;
  return NEW;
end
$function$
;
