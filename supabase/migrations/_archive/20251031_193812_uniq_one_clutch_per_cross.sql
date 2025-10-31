-- Allow at most one clutch per cross (needed for ON CONFLICT (cross_instance_id))
ALTER TABLE public.clutch_instances
  ADD CONSTRAINT IF NOT EXISTS uq_clutch_per_cross
  UNIQUE (cross_instance_id);
