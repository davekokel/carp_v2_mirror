BEGIN;

ALTER TABLE public.tanks
DROP CONSTRAINT IF EXISTS tanks_one_per_instance_unique_v11;

COMMIT;
