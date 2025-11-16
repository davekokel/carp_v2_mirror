BEGIN;

-- We no longer want a "one treated_clutch per clutch_instance" rule.
-- Drop the legacy constraint if it exists.
ALTER TABLE public.treated_clutches
  DROP CONSTRAINT IF EXISTS uq_treated_clutches_one_per_clutch;

-- Ensure we have exactly one unique constraint: (clutch_instance_id, treated_clutch_code)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM   pg_constraint
    WHERE  conrelid = 'public.treated_clutches'::regclass
    AND    conname  = 'uq_treated_clutches_per_code'
  ) THEN
    ALTER TABLE public.treated_clutches
      ADD CONSTRAINT uq_treated_clutches_per_code
      UNIQUE (clutch_instance_id, treated_clutch_code);
  END IF;
END$$;

COMMIT;
