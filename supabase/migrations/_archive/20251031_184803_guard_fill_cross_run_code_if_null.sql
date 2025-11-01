-- Backfill any historical NULLs first
UPDATE public.cross_instances ci
SET run_nn = COALESCE(ci.run_nn, public.next_run_nn(ci.tank_pair_code)),
    cross_run_code = COALESCE(ci.cross_run_code, format('TP-%s-%02s', ci.tank_pair_code, COALESCE(ci.run_nn, 1)))
WHERE ci.run_nn IS NULL OR ci.cross_run_code IS NULL;

-- AFTER INSERT guard: if BEFORE trigger missed, fill now
CREATE OR REPLACE FUNCTION public.trg_cross_instances_fill_if_null()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.run_nn IS NULL THEN
    NEW.run_nn := public.next_run_nn(NEW.tank_pair_code);
  END IF;

  IF NEW.cross_run_code IS NULL THEN
    NEW.cross_run_code := format('TP-%s-%02s', NEW.tank_pair_code, NEW.run_nn);
  END IF;

  -- write-through in case other code reads the row after AFTER INSERT
  UPDATE public.cross_instances
     SET run_nn = NEW.run_nn,
         cross_run_code = NEW.cross_run_code
   WHERE id = NEW.id;

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_cross_instances_fill_if_null ON public.cross_instances;
CREATE TRIGGER trg_cross_instances_fill_if_null
AFTER INSERT ON public.cross_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_cross_instances_fill_if_null();
