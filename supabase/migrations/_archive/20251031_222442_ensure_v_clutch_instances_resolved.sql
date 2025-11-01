DO $$
BEGIN
  IF to_regclass('public.v_clutch_instances') IS NULL THEN
    RAISE EXCEPTION 'v_clutch_instances not found';
  END IF;

  IF to_regclass('public.v_clutch_instances_resolved') IS NULL THEN
    EXECUTE 'CREATE VIEW public.v_clutch_instances_resolved AS SELECT * FROM public.v_clutch_instances';
  END IF;
END
$$;
