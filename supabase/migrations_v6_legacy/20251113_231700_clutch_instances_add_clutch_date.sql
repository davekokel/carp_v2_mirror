BEGIN;

-- 1) Add the new column
ALTER TABLE public.clutch_instances
  ADD COLUMN clutch_date date;

-- 2) Backfill from cross.created_at (or fallback to clutch.created_at)
UPDATE public.clutch_instances ci
SET clutch_date = COALESCE(cr.created_at::date, ci.created_at::date)
FROM public.crosses cr
WHERE cr.id = ci.cross_instance_id
  AND ci.clutch_date IS NULL;

COMMIT;
