BEGIN;

ALTER TABLE public.fish_instances_v10
  ADD COLUMN IF NOT EXISTS instance_stage text;

COMMENT ON COLUMN public.fish_instances_v10.instance_stage IS
  'Stage for this fish instance (e.g. injections, p0, f1, f2, stable, founder).';

COMMIT;
