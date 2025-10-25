BEGIN;

ALTER TABLE public.cross_plans
ADD COLUMN IF NOT EXISTS plan_title text,
ADD COLUMN IF NOT EXISTS plan_nickname text;

-- helpful index for searching by title/nickname
CREATE INDEX IF NOT EXISTS idx_cross_plans_title ON public.cross_plans (plan_title);
CREATE INDEX IF NOT EXISTS idx_cross_plans_nick ON public.cross_plans (plan_nickname);

COMMIT;
