-- Reformat cross_run_code as "<tank_pair_code>-NN" with zero-padded NN
CREATE OR REPLACE FUNCTION public.trg_cross_instances_set_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.run_nn IS NULL THEN
    NEW.run_nn := public.next_run_nn(NEW.tank_pair_code);
  END IF;

  IF NEW.cross_run_code IS NULL THEN
    NEW.cross_run_code := format('%s-%s', NEW.tank_pair_code, lpad(NEW.run_nn::text, 2, '0'));
  END IF;

  RETURN NEW;
END
$$;

-- Backfill any existing rows that don't match the expected format
UPDATE public.cross_instances ci
SET cross_run_code = format('%s-%s', ci.tank_pair_code, lpad(ci.run_nn::text, 2, '0'))
WHERE ci.run_nn IS NOT NULL
  AND ci.cross_run_code IS DISTINCT FROM format('%s-%s', ci.tank_pair_code, lpad(ci.run_nn::text, 2, '0'));
