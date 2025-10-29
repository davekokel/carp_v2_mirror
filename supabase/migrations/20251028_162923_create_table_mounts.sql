BEGIN;

CREATE TABLE IF NOT EXISTS public.mounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_instance_id uuid NOT NULL REFERENCES public.clutch_instances(id) ON DELETE CASCADE,
  mount_code text UNIQUE NOT NULL,
  time_mounted timestamptz NOT NULL DEFAULT now(),
  mounting_orientation text NOT NULL,
  n_top int DEFAULT 0,
  n_bottom int DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS ix_mounts_clutch_instance_id ON public.mounts(clutch_instance_id);
CREATE INDEX IF NOT EXISTS ix_mounts_time_mounted ON public.mounts(time_mounted DESC);

COMMIT;
