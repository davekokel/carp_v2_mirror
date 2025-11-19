BEGIN;

-- imaging_pairs was an earlier experiment; v8 uses imaging_clutch_memberships
-- and imaging_slots instead.
DROP TABLE IF EXISTS public.imaging_pairs CASCADE;

COMMIT;
