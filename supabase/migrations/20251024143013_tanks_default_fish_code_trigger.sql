BEGIN;

-- 1) Function: default fish_code from tank_code when missing
CREATE OR REPLACE FUNCTION public.tanks_default_fish_code()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  -- If fish_code was not provided, try to infer it from TANK-<fish_code>-#N
  IF NEW.fish_code IS NULL OR NEW.fish_code = '' THEN
    NEW.fish_code := (SELECT m[1]
                      FROM regexp_matches(COALESCE(NEW.tank_code,''), '^TANK-([A-Za-z0-9\-]+)-#\d+$') AS m
                      LIMIT 1);
  END IF;
  RETURN NEW;
END
$fn$;

-- 2) Trigger: run on INSERTs into public.tanks
DROP TRIGGER IF EXISTS trg_tanks_default_fish_code ON public.tanks;
CREATE TRIGGER trg_tanks_default_fish_code
BEFORE INSERT ON public.tanks
FOR EACH ROW
EXECUTE FUNCTION public.tanks_default_fish_code();

-- 3) Backfill: set fish_code where it is currently NULL but tank_code matches the convention
UPDATE public.tanks t
SET fish_code = s.fc
FROM (
  SELECT tank_id,
         (regexp_matches(tank_code, '^TANK-([A-Za-z0-9\-]+)-#\d+$'))[1] AS fc
  FROM public.tanks
) s
WHERE t.tank_id = s.tank_id
  AND t.fish_code IS NULL
  AND s.fc IS NOT NULL;

COMMIT;
