CREATE OR REPLACE FUNCTION public.trg_clutch_instance_code_fill()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
declare
  v_run  text;
  v_base text;
  v_code text;
  i      int := 1;
begin
  if new.clutch_instance_code is not null and btrim(new.clutch_instance_code) <> '' then
    return new;
  end if;

  -- Get the cross run code for this clutch's cross_instance
  select ci.cross_run_code into v_run
  from public.cross_instances ci
  where ci.id = new.cross_instance_id;

  -- Build the base code; if no run (shouldn't happen), use a safe fallback
  v_base := 'CI-' || coalesce(v_run, 'UNSET');

  v_code := v_base;

  -- If the base already exists, append -02, -03, ... until unique
  while exists (select 1 from public.clutches c where c.clutch_instance_code = v_code) loop
    i := i + 1;
    v_code := v_base || '-' || lpad(i::text, 2, '0');
  end loop;

  new.clutch_instance_code := v_code;
  return new;
end$function$
;
