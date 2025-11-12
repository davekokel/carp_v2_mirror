BEGIN;
ALTER TABLE public.plates
  ADD COLUMN IF NOT EXISTS nickname text;
COMMIT;
