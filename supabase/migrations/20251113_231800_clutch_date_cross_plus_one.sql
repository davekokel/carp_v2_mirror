BEGIN;

-- Set clutch_date = cross.created_at::date + 1 day for all existing clutches
UPDATE public.clutch_instances ci
SET clutch_date = (cr.created_at + interval '1 day')::date
FROM public.crosses cr
WHERE cr.id = ci.cross_instance_id;

COMMIT;
