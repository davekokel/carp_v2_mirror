DO $$
DECLARE
  code_trg_name text := NULL;
  code_fn_regproc text := NULL;
BEGIN
  -- Locate any clutch trigger whose function references gen_clutch_instance_code()
  SELECT t.tgname, (p.oid::regprocedure)::text
    INTO code_trg_name, code_fn_regproc
  FROM pg_trigger t
  JOIN pg_proc p ON p.oid = t.tgfoid
  WHERE t.tgrelid = 'public.clutch_instances'::regclass
    AND NOT t.tgisinternal
    AND (
      p.proname ILIKE '%gen_clutch_instance_code%' OR
      pg_get_functiondef(p.oid) ILIKE '%gen_clutch_instance_code(%'
    )
  LIMIT 1;

  -- Ensure our "ensure cross" BEFORE trigger exists (must run FIRST)
  -- This function was created earlier as public.trg_clutch_ensure_cross(); recreate idempotently.
  CREATE OR REPLACE FUNCTION public.trg_clutch_ensure_cross()
  RETURNS trigger
  LANGUAGE plpgsql
  AS $fc$
  DECLARE v_tp text; v_run int; v_code text;
  BEGIN
    PERFORM 1 FROM public.cross_instances ci WHERE ci.id = NEW.cross_instance_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'linked cross not found'; END IF;

    SELECT tank_pair_code, run_nn, cross_run_code
      INTO v_tp, v_run, v_code
    FROM public.cross_instances
    WHERE id = NEW.cross_instance_id;

    IF v_code IS NULL THEN
      IF v_run IS NULL THEN v_run := public.next_run_nn(v_tp); END IF;
      v_code := format('TP-%s-%02s', v_tp, v_run);
      UPDATE public.cross_instances
         SET run_nn = v_run,
             cross_run_code = v_code
       WHERE id = NEW.cross_instance_id;
    END IF;

    IF NEW.tank_pair_code IS NULL THEN NEW.tank_pair_code := v_tp; END IF;
    RETURN NEW;
  END
  $fc$;

  -- Drop any existing ensure trigger so we can recreate it FIRST
  IF EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgrelid='public.clutch_instances'::regclass
      AND tgname = 'trg_clutch_ensure_cross'
  ) THEN
    EXECUTE 'DROP TRIGGER trg_clutch_ensure_cross ON public.clutch_instances';
  END IF;

  -- Recreate ENSURE trigger first (so it runs before any code generators)
  EXECUTE 'CREATE TRIGGER trg_clutch_ensure_cross
           BEFORE INSERT ON public.clutch_instances
           FOR EACH ROW
           EXECUTE FUNCTION public.trg_clutch_ensure_cross()';

  -- If we found an existing code trigger, drop and recreate it so it runs AFTER ensure
  IF code_trg_name IS NOT NULL AND code_fn_regproc IS NOT NULL THEN
    EXECUTE format('DROP TRIGGER %I ON public.clutch_instances', code_trg_name);
    EXECUTE format('CREATE TRIGGER trg_clutch_set_code_after_ensure
                    BEFORE INSERT ON public.clutch_instances
                    FOR EACH ROW
                    EXECUTE FUNCTION %s', code_fn_regproc);
  END IF;
END
$$;
