DO $$
BEGIN
  -- 1) Relax NOT NULL on clutch_id (if currently NOT NULL)
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='planned_crosses'
      AND column_name='clutch_id'
      AND is_nullable='NO'
  ) THEN
    ALTER TABLE public.planned_crosses ALTER COLUMN clutch_id DROP NOT NULL;
  END IF;

  -- 2) Enable RLS and install idempotent policies
  ALTER TABLE public.planned_crosses ENABLE ROW LEVEL SECURITY;

  -- Cleanup a previous bad policy name if it exists
  IF EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.planned_crosses'::regclass
      AND polname='app_rw_upsert_planned_crosses'
  ) THEN
    DROP POLICY app_rw_upsert_planned_crosses ON public.planned_crosses;
  END IF;

  -- SELECT policy
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

  -- INSERT policy
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.planned_crosses'::regclass
      AND polname='app_rw_insert_planned_crosses'
  ) THEN
    CREATE POLICY app_rw_insert_planned_crosses
      ON public.planned_crosses
      FOR INSERT
      TO app_rw
      WITH CHECK (true);
  END IF;

  -- UPDATE policy
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.planned_crosses'::regclass
      AND polname='app_rw_update_planned_crosses'
  ) THEN
    CREATE POLICY app_rw_update_planned_crosses
      ON public.planned_crosses
      FOR UPDATE
      TO app_rw
      USING (true)
      WITH CHECK (true);
  END IF;
END
$$ LANGUAGE plpgsql;
