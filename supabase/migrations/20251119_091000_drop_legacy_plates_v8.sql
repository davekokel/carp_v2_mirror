BEGIN;

-- v8: drop legacy plates table (replaced by imaging_plates)
DROP TABLE IF EXISTS public.plates;

COMMIT;
