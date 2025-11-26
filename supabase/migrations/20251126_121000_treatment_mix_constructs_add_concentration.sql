BEGIN;

-- v10: allow v10_load_treatments_from_csv.py to store construct concentrations
-- like "25 ng/µL" on each treatment mix.

ALTER TABLE public.treatment_mix_constructs
  ADD COLUMN IF NOT EXISTS concentration text;

COMMIT;
