BEGIN;

-- Drop the old "one per clutch" constraint
ALTER TABLE public.treated_clutches
  DROP CONSTRAINT IF EXISTS uq_treated_clutches_one_per_clutch;

-- Enforce uniqueness per (clutch_instance_id, treated_clutch_code)
ALTER TABLE public.treated_clutches
  ADD CONSTRAINT uq_treated_clutches_per_code
  UNIQUE (clutch_instance_id, treated_clutch_code);

COMMIT;
