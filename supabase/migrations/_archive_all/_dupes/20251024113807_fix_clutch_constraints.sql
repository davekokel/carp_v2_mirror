BEGIN;
ALTER TABLE public.clutch_instances
  DROP CONSTRAINT IF EXISTS clutch_instance_code_shape,
  ADD CONSTRAINT clutch_instance_code_shape
  CHECK (clutch_instance_code ~ '^CL\([A-Z0-9-]+\)\([0-9]{6}\)\([0-9]{2}\)$');

CREATE UNIQUE INDEX IF NOT EXISTS uq_clutch_instance_code
  ON public.clutch_instances (clutch_instance_code);
COMMIT;
