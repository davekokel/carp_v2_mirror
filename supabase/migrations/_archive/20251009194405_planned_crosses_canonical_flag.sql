BEGIN;
ALTER TABLE public.planned_crosses ADD COLUMN IF NOT EXISTS is_canonical boolean NOT NULL DEFAULT true;
-- mark newest as canonical per trio (only if you preload planned_crosses; harmless if empty)
WITH ranked AS (
  SELECT id_uuid, clutch_id, mother_tank_id, father_tank_id,
         ROW_NUMBER() OVER (PARTITION BY clutch_id, mother_tank_id, father_tank_id
                            ORDER BY created_at DESC, id_uuid DESC) rn
  FROM public.planned_crosses
  WHERE mother_tank_id IS NOT NULL AND father_tank_id IS NOT NULL
)
UPDATE public.planned_crosses pc
SET is_canonical = (r.rn = 1)
FROM ranked r WHERE pc.id_uuid = r.id_uuid;
-- Enforce one canonical per (clutch_id, parents) moving forward
CREATE UNIQUE INDEX IF NOT EXISTS uq_planned_crosses_clutch_parents_canonical
  ON public.planned_crosses(clutch_id, mother_tank_id, father_tank_id)
  WHERE is_canonical = true
    AND mother_tank_id IS NOT NULL AND father_tank_id IS NOT NULL;
COMMIT;
