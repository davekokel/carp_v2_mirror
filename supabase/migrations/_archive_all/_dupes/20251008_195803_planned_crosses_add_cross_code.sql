BEGIN;
ALTER TABLE public.planned_crosses
ADD COLUMN IF NOT EXISTS cross_code text;
COMMIT;
