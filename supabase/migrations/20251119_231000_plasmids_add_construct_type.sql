BEGIN;

ALTER TABLE public.plasmids
  ADD COLUMN IF NOT EXISTS construct_type text;

COMMIT;
