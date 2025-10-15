-- 1) Fix RLS helper (use pg_policy, not pg_policy)
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

-- 2) Relax NOT NULL on clutch_id so insert/upsert can succeed without a pre-linked clutch
DO $$
BEGIN
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='planned_crosses'
      and column_name='clutch_id' and is_nullable='NO'
  ) then
    execute 'alter table public.planned_crosses alter column clutch_id drop not null';
  end if;
end
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  EXECUTE 'ALTER TABLE public.planned_crosses ENABLE ROW LEVEL SECURITY';

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='planned_crosses'
      AND policyname='app_rw_select_planned_crosses'
  ) THEN
    EXECUTE 'CREATE POLICY app_rw_select_planned_crosses ON public.planned_crosses FOR SELECT TO app_rw USING (true)';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='planned_crosses'
      AND policyname='app_rw_insert_planned_crosses'
  ) THEN
    EXECUTE 'CREATE POLICY app_rw_insert_planned_crosses ON public.planned_crosses FOR INSERT TO app_rw WITH CHECK (true)';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='planned_crosses'
      AND policyname='app_rw_update_planned_crosses'
  ) THEN
    EXECUTE 'CREATE POLICY app_rw_update_planned_crosses ON public.planned_crosses FOR UPDATE TO app_rw USING (true) WITH CHECK (true)';
  END IF;
END;
$$ LANGUAGE plpgsql;

