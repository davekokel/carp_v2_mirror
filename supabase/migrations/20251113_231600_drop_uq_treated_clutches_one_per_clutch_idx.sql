BEGIN;

-- This is a left-over unique index on clutch_instance_id only.
-- It conflicts with the new design of multiple groups per clutch.
DROP INDEX IF EXISTS public.uq_treated_clutches_one_per_clutch;

COMMIT;
