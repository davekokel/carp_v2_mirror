BEGIN;

-- A) Deduplicate: keep the newest row per (clutch_id, mother_tank_id, father_tank_id)
WITH ranked AS (
    SELECT
        id_uuid,
        clutch_id,
        mother_tank_id,
        father_tank_id,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY clutch_id, mother_tank_id, father_tank_id
            ORDER BY created_at DESC, id_uuid DESC
        ) AS rn
    FROM public.planned_crosses
    WHERE
        mother_tank_id IS NOT NULL
        AND father_tank_id IS NOT NULL
)

DELETE FROM public.planned_crosses pc
USING ranked r
WHERE
    pc.id_uuid = r.id_uuid
    AND r.rn > 1;

-- B) Enforce uniqueness for "identical concept": same clutch + same mother/father tanks
-- Partial unique index so it doesn't fire when tanks are empty/null.
CREATE UNIQUE INDEX IF NOT EXISTS uq_planned_crosses_clutch_parents
ON public.planned_crosses (clutch_id, mother_tank_id, father_tank_id)
WHERE mother_tank_id IS NOT NULL AND father_tank_id IS NOT NULL;

COMMIT;
