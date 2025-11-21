BEGIN;

UPDATE public.crosses
SET cross_run_code = 'CR-' || left(id::text, 8)
WHERE cross_run_code IS NULL;

COMMIT;
