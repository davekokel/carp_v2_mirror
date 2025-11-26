BEGIN;

ALTER TABLE public.treatment_mix_dyes
  ADD COLUMN IF NOT EXISTS concentration text;

COMMIT;
