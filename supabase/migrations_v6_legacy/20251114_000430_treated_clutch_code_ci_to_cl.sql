BEGIN;

-- Normalize treated_clutch_code prefix: CI- → CL-
UPDATE public.treated_clutches
SET treated_clutch_code = regexp_replace(treated_clutch_code, '^CI-', 'CL-')
WHERE treated_clutch_code LIKE 'CI-%';

COMMIT;
