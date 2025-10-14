DO $$
DECLARE v RECORD;
BEGIN
  FOR v IN
    SELECT table_name AS view_name
    FROM information_schema.columns
    WHERE table_schema='public' AND column_name='id_uuid'
      AND table_name IN (SELECT viewname FROM pg_views WHERE schemaname='public')
  LOOP
    BEGIN
      EXECUTE format('ALTER VIEW public.%I RENAME COLUMN id_uuid TO id', v.view_name);
      RAISE NOTICE 'Renamed column id_uuid -> id on view %', v.view_name;
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE 'Skip rename on view %: %', v.view_name, SQLERRM;
    END;
  END LOOP;
END $$;
