BEGIN;

DO $$
DECLARE
  n_mom int;
  n_dad int;
BEGIN
  SELECT count(*) INTO n_mom FROM public.tank_crosses WHERE mom_tank_id IS NULL;
  SELECT count(*) INTO n_dad FROM public.tank_crosses WHERE dad_tank_id IS NULL;

  IF n_mom > 0 OR n_dad > 0 THEN
    RAISE EXCEPTION 'Cannot enforce NOT NULL: % rows have mom_tank_id NULL, % rows have dad_tank_id NULL',
      n_mom, n_dad;
  END IF;
END$$;

ALTER TABLE public.tank_crosses
  ALTER COLUMN mom_tank_id SET NOT NULL,
  ALTER COLUMN dad_tank_id SET NOT NULL;

COMMIT;
