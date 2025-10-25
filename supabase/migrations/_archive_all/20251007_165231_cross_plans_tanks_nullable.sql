BEGIN;

-- Make tank A/B optional on cross_plans
ALTER TABLE public.cross_plans
ALTER COLUMN tank_a_id DROP NOT NULL,
ALTER COLUMN tank_b_id DROP NOT NULL;

-- Keep partial uniqueness that only applies when both are present (you already added these earlier)
-- Recreate defensively in case they don't exist yet
CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_plans_day_tankpair
ON public.cross_plans (plan_date, tank_a_id, tank_b_id)
WHERE tank_a_id IS NOT NULL AND tank_b_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_plans_day_fishpair
ON public.cross_plans (plan_date, mother_fish_id, father_fish_id)
WHERE mother_fish_id IS NOT NULL AND father_fish_id IS NOT NULL;

COMMIT;
