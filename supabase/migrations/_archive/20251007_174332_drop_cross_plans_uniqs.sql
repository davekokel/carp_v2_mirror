BEGIN;

-- You may have one or both of these from earlier:
--  - uq_cross_plans_day_fishpair (partial unique by day, mother_fish_id, father_fish_id)
--  - uq_cross_plans_day_tankpair (partial unique by day, tank_a_id, tank_b_id);
DO 28762
BEGIN
  IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_cross_plans_day_fishpair') THEN
    DROP INDEX public.uq_cross_plans_day_fishpair;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_cross_plans_day_tankpair') THEN
    DROP INDEX public.uq_cross_plans_day_tankpair;
  END IF;
END$$;

-- (Optional) replace with non-unique helpers for search speed
CREATE INDEX IF NOT EXISTS idx_cross_plans_day_mother ON public.cross_plans(plan_date, mother_fish_id);
CREATE INDEX IF NOT EXISTS idx_cross_plans_day_father ON public.cross_plans(plan_date, father_fish_id);

COMMIT;
