DO $$
DECLARE
  code_fn_regproc text := NULL;
BEGIN
  -- Find the ORIGINAL trigger function that calls gen_clutch_instance_code()
  SELECT (p.oid::regprocedure)::text
    INTO code_fn_regproc
  FROM pg_proc p
  WHERE p.pronamespace='public'::regnamespace
    AND (
      p.proname ILIKE '%gen_clutch_instance_code%' OR
      pg_get_functiondef(p.oid) ILIKE '%gen_clutch_instance_code(%'
    )
  ORDER BY p.oid DESC
  LIMIT 1;

  -- If our helper trigger exists and points to our helper function, drop it
  IF EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgrelid='public.clutch_instances'::regclass
      AND NOT tgisinternal
      AND tgname='zz_clutch_set_code'
      AND tgfoid = 'public.trg_clutch_set_code_from_fn()'::regprocedure
  ) THEN
    EXECUTE 'DROP TRIGGER zz_clutch_set_code ON public.clutch_instances';
  END IF;

  -- If we can find the real code trigger function, recreate zz_clutch_set_code to call it
  IF code_fn_regproc IS NOT NULL THEN
    EXECUTE format(
      'CREATE TRIGGER zz_clutch_set_code
       BEFORE INSERT ON public.clutch_instances
       FOR EACH ROW
       EXECUTE FUNCTION %s',
      code_fn_regproc
    );
  END IF;

  -- Remove our helper function if it exists
  IF EXISTS (SELECT 1 FROM pg_proc WHERE pronamespace='public'::regnamespace AND proname='trg_clutch_set_code_from_fn') THEN
    EXECUTE 'DROP FUNCTION public.trg_clutch_set_code_from_fn() CASCADE';
  END IF;
END
$$;

-- Belt-and-suspenders: ensure no column DEFAULT remains on clutch_instance_code
ALTER TABLE public.clutch_instances
  ALTER COLUMN clutch_instance_code DROP DEFAULT;
