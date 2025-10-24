BEGIN;

-- 1) Ensure created_by uses UUID consistently when inserting from app or triggers
-- Create or replace a trigger function to coerce text → uuid where needed
CREATE OR REPLACE FUNCTION public.tanks_cast_created_by_uuid()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  -- If incoming created_by is TEXT, try to coerce to UUID or NULL
  IF pg_typeof(NEW.created_by)::text = 'text' THEN
    BEGIN
      NEW.created_by := (NEW.created_by)::uuid;
    EXCEPTION WHEN others THEN
      NEW.created_by := NULL;
    END;
  END IF;
  RETURN NEW;
END
$fn$;

-- 2) Drop any existing trigger (safe even if none exists)
DROP TRIGGER IF EXISTS trg_tanks_cast_created_by_uuid ON public.tanks;

-- 3) Recreate it
CREATE TRIGGER trg_tanks_cast_created_by_uuid
BEFORE INSERT OR UPDATE ON public.tanks
FOR EACH ROW
EXECUTE FUNCTION public.tanks_cast_created_by_uuid();

-- 4) Backfill: if some rows still have text type (from earlier imports), cast them
DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT tank_id, created_by
    FROM public.tanks
    WHERE created_by IS NOT NULL
      AND created_by !~* '^[0-9a-f-]{36}$'  -- not UUID format
  LOOP
    BEGIN
      UPDATE public.tanks
         SET created_by = NULL
       WHERE tank_id = r.tank_id;
    EXCEPTION WHEN others THEN
      -- silently skip malformed rows
      CONTINUE;
    END;
  END LOOP;
END$$;

COMMIT;
