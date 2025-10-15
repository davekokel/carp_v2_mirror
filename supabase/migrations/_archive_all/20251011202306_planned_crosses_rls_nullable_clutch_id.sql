DO $$
BEGIN
  EXECUTE 'ALTER TABLE public.planned_crosses ENABLE ROW LEVEL SECURITY';
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='planned_crosses' AND policyname='app_rw_select_planned_crosses') THEN
    EXECUTE 'CREATE POLICY app_rw_select_planned_crosses ON public.planned_crosses FOR SELECT TO app_rw USING (true)';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='planned_crosses' AND policyname='app_rw_insert_planned_crosses') THEN
    EXECUTE 'CREATE POLICY app_rw_insert_planned_crosses ON public.planned_crosses FOR INSERT TO app_rw WITH CHECK (true)';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='planned_crosses' AND policyname='app_rw_update_planned_crosses') THEN
    EXECUTE 'CREATE POLICY app_rw_update_planned_crosses ON public.planned_crosses FOR UPDATE TO app_rw USING (true) WITH CHECK (true)';
  END IF;
END;
$$ LANGUAGE plpgsql;
