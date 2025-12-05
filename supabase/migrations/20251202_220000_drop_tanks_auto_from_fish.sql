BEGIN;

DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT tgname
    FROM pg_trigger
    WHERE tgrelid = 'public.fish_instances_v10'::regclass
      AND NOT tgisinternal
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.fish_instances_v10;', r.tgname);
  END LOOP;
END$$;

DELETE FROM public.tanks t
WHERE t.tank_code LIKE 'TANK-FSH-%-001'
  AND EXISTS (
    SELECT 1
    FROM public.tanks t2
    WHERE t2.fish_instance_id = t.fish_instance_id
      AND t2.tank_code LIKE 'TANK-FSH-%-T1'
  );

COMMIT;
