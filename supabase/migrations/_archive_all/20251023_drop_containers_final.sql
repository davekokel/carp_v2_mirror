BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='containers'
  ) THEN
    -- Check dependencies before dropping
    PERFORM 1
    FROM pg_constraint
    WHERE confrelid = 'public.containers'::regclass;
    IF NOT FOUND THEN
      EXECUTE 'DROP TABLE public.containers CASCADE';
      RAISE NOTICE 'Dropped public.containers';
    ELSE
      RAISE NOTICE 'Skipping drop: public.containers still referenced.';
    END IF;
  END IF;
END$$;

COMMIT;
