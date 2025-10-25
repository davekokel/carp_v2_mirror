BEGIN;

ALTER TABLE public.cross_plans DROP CONSTRAINT IF EXISTS uq_cross_plans_unique;

CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_plans_day_tankpair
ON public.cross_plans (plan_date, tank_a_id, tank_b_id)
WHERE tank_a_id IS NOT NULL AND tank_b_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_plans_day_fishpair
ON public.cross_plans (plan_date, mother_fish_id, father_fish_id)
WHERE mother_fish_id IS NOT NULL AND father_fish_id IS NOT NULL;

COMMIT;
