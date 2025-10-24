BEGIN;

DROP TRIGGER IF EXISTS trg_clutch_instances_set_code ON public.clutch_instances;
DROP FUNCTION IF EXISTS public.tg_clutch_instances_set_code();

CREATE FUNCTION public.tg_clutch_instances_set_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  tp_code text;
  run_code text;
  run_date date;
  seq_text text;
  birth_d  date;
BEGIN
  IF NEW.clutch_instance_code IS NOT NULL THEN
    RETURN NEW;
  END IF;

  IF NEW.cross_instance_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT ci.cross_run_code, ci.cross_date, tp.tank_pair_code
    INTO run_code, run_date, tp_code
  FROM public.cross_instances ci
  JOIN public.tank_pairs tp ON tp.id = ci.tank_pair_id
  WHERE ci.id = NEW.cross_instance_id;

  SELECT substring(run_code from '\(([0-9]{2})\)$') INTO seq_text;
  birth_d := COALESCE(NEW.birthday, run_date + INTERVAL '1 day');

  NEW.clutch_instance_code :=
    format('CL(%s)(%s)(%s)',
           tp_code,
           to_char(birth_d, 'YYMMDD'),
           COALESCE(seq_text, '01'));

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_clutch_instances_set_code
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.tg_clutch_instances_set_code();

COMMIT;
