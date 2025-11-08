BEGIN;
ALTER TABLE public.dyes ADD COLUMN IF NOT EXISTS localization text;
COMMIT;
