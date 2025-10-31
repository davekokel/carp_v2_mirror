-- Fix trigger for cross_instances: stop referencing run_nn column
DO $$
BEGIN
  -- Drop old trigger if exists
  IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_cross_instances_set_code') THEN
    EXECUTE 'DROP TRIGGER trg_cross_instances_set_code ON public.cross_instances';
  END IF;
  -- Drop old function if exists
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'trg_cross_instances_set_code') THEN
    EXECUTE 'DROP FUNCTION public.trg_cross_instances_set_code()';
  END IF;
END $$;

-- Recreate function with run_nn computed dynamically
CREATE FUNCTION public.trg_cross_instances_set_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  next_nn int;
  tp_code text;
BEGIN
  -- Derive next run number via advisory-locked sequence
  next_nn := public.next_run_nn(NEW.tank_pair_code);
  tp_code := NEW.tank_pair_code;

  -- Set cross_run_code like "TP-2500001-03"
  NEW.cross_run_code := format('%s-%02s', tp_code, next_nn);
  RETURN NEW;
END;
$$;

-- Recreate trigger on cross_instances
CREATE TRIGGER trg_cross_instances_set_code
BEFORE INSERT ON public.cross_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_cross_instances_set_code();

COMMENT ON FUNCTION public.trg_cross_instances_set_code() IS
  'Before-insert trigger for cross_instances: generates cross_run_code using next_run_nn(tank_pair_code)';
