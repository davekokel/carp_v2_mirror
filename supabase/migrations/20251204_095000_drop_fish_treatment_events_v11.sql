BEGIN;

-- Drop the mis-modeled fish_treatment_events_v11 table.
-- Treatments/injections in v11 are modeled at the clutch level
-- (via clutches / treated_clutches_v11 / join_clutch_treatments),
-- not per fish_instance.

DROP TABLE IF EXISTS public.fish_treatment_events_v11;

COMMIT;
