DO $$
BEGIN
DECLARE
  t text;
  v RECORD;
  tables text[] := ARRAY[
    'clutch_plans',
    'clutches',
    'containers',
    'cross_instances',
    'crosses',
    'fish',
    'planned_crosses'
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    FOR v IN
      SELECT view_schema, view_name
      FROM information_schema.view_column_usage
      WHERE table_schema='public'
        AND table_name=t
        AND column_name='id_uuid'
    LOOP
      IF v.view_schema = 'public' THEN
        EXECUTE format('DROP VIEW IF EXISTS public.%I', v.view_name);
        RAISE NOTICE 'Dropped view public.%', v.view_name;
      ELSE
        RAISE NOTICE 'Skipping non-public view %.%', v.view_schema, v.view_name;
      END IF;
    END LOOP;

    BEGIN
      EXECUTE format('ALTER TABLE public.%I DROP COLUMN id_uuid', t);
      RAISE NOTICE 'Dropped public.%.id_uuid', t;
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE 'Could not drop public.%.id_uuid: %', t, SQLERRM;
    END;
  END LOOP;
END;
END;
$$ LANGUAGE plpgsql;
