DO $$
DECLARE
  code_trg_name text := NULL;
  code_fn_regproc text := NULL;
  stmt text;
BEGIN
  -- Find any BEFORE trigger that calls gen_clutch_instance_code()
  SELECT t.tgname, (p.oid::regprocedure)::text
    INTO code_trg_name, code_fn_regproc
  FROM pg_trigger t
  JOIN pg_proc p ON p.oid = t.tgfoid
  WHERE t.tgrelid='public.clutch_instances'::regclass
    AND NOT t.tgisinternal
    AND (
      p.proname ILIKE '%gen_clutch_instance_code%' OR
      pg_get_functiondef(p.oid) ILIKE '%gen_clutch_instance_code(%'
    )
  LIMIT 1;

  -- Ensure the ENSURE-FIRST trigger is in place with an early-sorting name
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

  -- Move the code trigger to a late-sorting name so it fires AFTER ensure
  IF code_trg_name IS NOT NULL AND code_fn_regproc IS NOT NULL THEN
    stmt := format('DROP TRIGGER IF EXISTS %I ON public.clutch_instances', code_trg_name);
    EXECUTE stmt;

    stmt := 'CREATE TRIGGER zz_clutch_set_code ' ||
            'BEFORE INSERT ON public.clutch_instances ' ||
            'FOR EACH ROW EXECUTE FUNCTION ' || code_fn_regproc;
    EXECUTE stmt;
  END IF;
END
$$;
