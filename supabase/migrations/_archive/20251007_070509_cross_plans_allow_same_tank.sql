BEGIN;
DO 28762
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema='public'
      AND table_name='cross_plans'
      AND constraint_type='CHECK'
      AND constraint_name='chk_distinct_tanks'
  ) THEN
    ALTER TABLE public.cross_plans DROP CONSTRAINT chk_distinct_tanks;
  END IF;
END$$;
COMMIT;
