BEGIN;

-- Drop the old "one per clutch" constraint on clutch_instance_id
ALTER TABLE public.treated_clutches
  DROP CONSTRAINT IF EXISTS uq_treated_clutches_one_per_clutch;

-- Re-add it with the *correct* semantics: unique per (clutch_instance_id, treated_clutch_code)
ALTER TABLE public.treated_clutches
  ADD CONSTRAINT uq_treated_clutches_one_per_clutch
  UNIQUE (clutch_instance_id, treated_clutch_code);

COMMIT;
