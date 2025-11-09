BEGIN;
ALTER TABLE public.fluors ADD COLUMN IF NOT EXISTS alt_names text;
ALTER TABLE public.tags   ADD COLUMN IF NOT EXISTS alt_names text;
COMMIT;
