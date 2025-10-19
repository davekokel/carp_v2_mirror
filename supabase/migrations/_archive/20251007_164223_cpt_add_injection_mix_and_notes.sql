BEGIN;

ALTER TABLE public.cross_plan_treatments
ADD COLUMN IF NOT EXISTS injection_mix text NULL,
ADD COLUMN IF NOT EXISTS treatment_notes text NULL;

COMMIT;
