BEGIN;

-- Make sure the columns exist on containers (no-ops if already present)
ALTER TABLE public.containers
  ADD COLUMN IF NOT EXISTS status_changed_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS activated_at     timestamptz NULL,
  ADD COLUMN IF NOT EXISTS deactivated_at   timestamptz NULL,
  ADD COLUMN IF NOT EXISTS last_seen_at     timestamptz NULL,
  ADD COLUMN IF NOT EXISTS last_seen_source text NULL;

-- Recreate the view with the richer column set
DROP VIEW IF EXISTS public.v_containers_crossing_candidates;
CREATE VIEW public.v_containers_crossing_candidates AS
SELECT
  id_uuid,
  container_type,
  label,
  status,
  created_by,
  created_at,
  status_changed_at,
  activated_at,
  deactivated_at,
  last_seen_at,
  note
FROM public.containers
WHERE container_type IN ('inventory_tank','crossing_tank','holding_tank','nursery_tank','petri_dish');

COMMIT;
