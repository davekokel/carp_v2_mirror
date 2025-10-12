DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='planned_crosses'
      AND column_name='clutch_id'
      AND is_nullable='NO'
  ) THEN
    ALTER TABLE public.planned_crosses ALTER COLUMN clutch_id DROP NOT NULL;
  END IF;

  ALTER TABLE public.planned_crosses ENABLE ROW LEVEL SECURITY;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.planned_crosses'::regclass
      AND polname='app_rw_select_planned_crosses'
  ) THEN
    CREATE POLICY app_rw_select_planned_crosses
      ON public.planned_crosses
      FOR SELECT
      TO app_rw
      USING (true);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.planned_crosses'::regclass
      AND polname='app_rw_upsert_planned_crosses'
  ) THEN
    CREATE POLICY app_rw_upsert_planned_crosses
      ON public.planned_crosses
      FOR INSERT, UPDATE
      TO app_rw
      USING (true)
      WITH CHECK (true);
  END IF;
END$$;
