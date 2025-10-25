BEGIN;

DROP TRIGGER IF EXISTS trg_clutch_instances_default_bday ON public.clutch_instances;
DROP FUNCTION IF EXISTS public.tg_clutch_instances_default_bday();

CREATE FUNCTION public.tg_clutch_instances_default_bday()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  d date;
BEGIN
  IF NEW.birthday IS NULL AND NEW.cross_instance_id IS NOT NULL THEN
    SELECT ci.cross_date INTO d FROM public.cross_instances ci WHERE ci.id = NEW.cross_instance_id;
    IF d IS NOT NULL THEN
      NEW.birthday := d + INTERVAL '1 day';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_clutch_instances_default_bday
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.tg_clutch_instances_default_bday();

COMMIT;
