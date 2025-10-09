BEGIN;
ALTER TABLE public.clutch_plans
  ADD COLUMN IF NOT EXISTS planned_name     text,
  ADD COLUMN IF NOT EXISTS planned_nickname text;
COMMIT;
