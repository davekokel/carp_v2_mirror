-- Ensure a clutch never inserts unless its linked cross exists and has cross_run_code
CREATE OR REPLACE FUNCTION public.trg_clutch_ensure_cross()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_tp text;
  v_run int;
  v_code text;
BEGIN
  -- Must have a linked cross
  PERFORM 1 FROM public.cross_instances ci WHERE ci.id = NEW.cross_instance_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'linked cross not found';
  END IF;

  -- Pull current cross fields
  SELECT tank_pair_code, run_nn, cross_run_code
    INTO v_tp, v_run, v_code
  FROM public.cross_instances
  WHERE id = NEW.cross_instance_id;

  -- If cross_run_code missing, fill it (and run_nn) now
  IF v_code IS NULL THEN
    -- assign run_nn if missing
    IF v_run IS NULL THEN
      v_run := public.next_run_nn(v_tp);
    END IF;

    v_code := format('TP-%s-%02s', v_tp, v_run);

    UPDATE public.cross_instances
       SET run_nn = v_run,
           cross_run_code = v_code
     WHERE id = NEW.cross_instance_id;
  END IF;

  -- Ensure clutch.tank_pair_code is aligned
  IF NEW.tank_pair_code IS NULL THEN
    NEW.tank_pair_code := v_tp;
  END IF;

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_clutch_ensure_cross ON public.clutch_instances;
CREATE TRIGGER trg_clutch_ensure_cross
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_clutch_ensure_cross();
