DO $$
BEGIN
  IF to_regclass('public.clutch_instances') IS NULL THEN
    RAISE NOTICE 'Skipping RLS: table public.clutch_instances not found in this DB.';
    RETURN;
  END IF;

  ALTER TABLE public.clutch_instances ENABLE ROW LEVEL SECURITY;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.clutch_instances'::regclass
      AND polname='app_rw_select_ci_annot'
  ) THEN
    CREATE POLICY app_rw_select_ci_annot
      ON public.clutch_instances FOR SELECT TO app_rw USING (true);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.clutch_instances'::regclass
      AND polname='app_rw_update_ci_annot'
  ) THEN
    CREATE POLICY app_rw_update_ci_annot
      ON public.clutch_instances FOR UPDATE TO app_rw
      USING (true) WITH CHECK (true);
  END IF;
END$$;
