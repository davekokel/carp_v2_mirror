BEGIN;

-- If join_fish_treatments exists, drop it and anything depending on it.
-- CARP v8 is clutch-centric: treatments attach to clutches (and imaging), not adult fish.
DROP TABLE IF EXISTS public.join_fish_treatments CASCADE;

COMMIT;
