DO $$
DECLARE
  -- Will capture any existing code trigger that references gen_clutch_instance_code()
  r record;
  code_trg_name text;
  code_fn_regproc text;
BEGIN
  -- 0) (Re)create the ENSURE trigger function (idempotent)
  CREATE OR REPLACE FUNCTION public.trg_clutch_ensure_cross()
  RETURNS trigger
  LANGUAGE plpgsql
  AS $fc$
  DECLARE v_tp text; v_run int; v_code text;
  BEGIN
    -- Linked cross must exist
    PERFORM 1 FROM public.cross_instances ci WHERE ci.id = NEW.cross_instance_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'linked cross not found';
    END IF;

    -- Pull cross fields, fill if missing
    SELECT tank_pair_code, run_nn, cross_run_code
      INTO v_tp, v_run, v_code
    FROM public.cross_instances
    WHERE id = NEW.cross_instance_id;

    IF v_code IS NULL THEN
      IF v_run IS NULL THEN
        v_run := public.next_run_nn(v_tp);
      END IF;
      v_code := format('TP-%s-%02s', v_tp, v_run);
      UPDATE public.cross_instances
         SET run_nn = v_run,
             cross_run_code = v_code
       WHERE id = NEW.cross_instance_id;
    END IF;

    IF NEW.tank_pair_code IS NULL THEN
      NEW.tank_pair_code := v_tp;
    END IF;

    RETURN NEW;
  END
  $fc$;

  -- 1) Drop any prior ensure trigger (any name), then create a first-sorting name
  IF EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgrelid='public.clutch_instances'::regclass
      AND NOT tgisinternal
      AND tgname = 'trg_clutch_ensure_cross'
  ) THEN
    EXECUTE 'DROP TRIGGER trg_clutch_ensure_cross ON public.clutch_instances';
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgrelid='public.clutch_instances'::regclass
      AND NOT tgisinternal
      AND tgname = 'aa_clutch_ensure_cross_first'
  ) THEN
    EXECUTE 'DROP TRIGGER aa_clutch_ensure_cross_first ON public.clutch_instances';
  END IF;

  EXECUTE 'CREATE TRIGGER aa_clutch_ensure_cross_first
           BEFORE INSERT ON public.clutch_instances
           FOR EACH ROW
           EXECUTE FUNCTION public.trg_clutch_ensure_cross()';

  -- 2) Find any BEFORE INSERT code trigger that references gen_clutch_instance_code and move it to a late-sorting name
  SELECT t.tgname, (p.oid::regprocedure)::text
    INTO code_trg_name, code_fn_regproc
  FROM pg_trigger t
  JOIN pg_proc p ON p.oid = t.tgfoid
  WHERE t.tgrelid='public.clutch_instances'::regclass
    AND NOT t.tgisinternal
    AND ( -- a code generator we want to run AFTER ensure
      p.proname ILIKE '%gen_clutch_instance_code%' OR
      pg_get_functiondef(p.oid) ILIKE '%gen_clutch_instance_code(%'
    )
  LIMIT 1;

  IF code_trg_name IS NOT NULL AND code_fn_regproc IS NOT NULL THEN
    -- Drop the existing code trigger (whatever it was named)
    EXECUTE format('DROP TRIGGER %I ON public.clutch_instances', code_trg_name);

    -- Recreate with a late-sorting name so it runs after the ensure trigger
    EXECUTE format($$
      CREATE TRIGGER zz_clutch_set_code
      BEFORE INSERT ON public.clutch_instances
      FOR EACH ROW
      EXECUTE FUNCTION %s
    $$, code_fn_regproc);
  END IF;
END
$$;
