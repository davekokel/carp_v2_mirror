BEGIN;

-- 1) Add the column if missing
ALTER TABLE public.tank_pairs
  ADD COLUMN IF NOT EXISTS updated_at timestamptz;

-- 2) Touch updated_at automatically on UPDATE
CREATE OR REPLACE FUNCTION public._touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- Recreate the trigger idempotently
DROP TRIGGER IF EXISTS trg_tank_pairs_touch_updated ON public.tank_pairs;
CREATE TRIGGER trg_tank_pairs_touch_updated
BEFORE UPDATE ON public.tank_pairs
FOR EACH ROW
EXECUTE FUNCTION public._touch_updated_at();

COMMIT;
