BEGIN;

ALTER TABLE public.treatments
  ADD COLUMN IF NOT EXISTS treatment_type text;

-- Seed existing rows with a default guess.
-- All current v10 seed treatments are injections (legacy_v9), so mark them as 'injection'.
UPDATE public.treatments
SET treatment_type = COALESCE(treatment_type, 'injection');

COMMIT;
