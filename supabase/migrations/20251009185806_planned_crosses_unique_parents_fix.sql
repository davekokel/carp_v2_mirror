BEGIN;

-- 1) Build a mapping dup_id -> canonical_id for planned_crosses with identical parents under same clutch_id
CREATE TEMP TABLE pc_dups_map ON COMMIT DROP AS
WITH norm AS (
  SELECT
    id_uuid,
    clutch_id,
    mother_tank_id,
    father_tank_id,
    created_at,
    ROW_NUMBER() OVER (
      PARTITION BY clutch_id, mother_tank_id, father_tank_id
      ORDER BY created_at DESC, id_uuid DESC       -- newest wins as canonical
    ) AS rn
  FROM public.planned_crosses
  WHERE mother_tank_id IS NOT NULL
    AND father_tank_id IS NOT NULL
),
canon AS (
  SELECT id_uuid AS canonical_id, clutch_id, mother_tank_id, father_tank_id
  FROM norm
  WHERE rn = 1
),
dups AS (
  SELECT n.id_uuid AS dup_id, c.canonical_id, n.clutch_id
  FROM norm n
  JOIN canon c
    ON c.clutch_id = n.clutch_id
   AND c.mother_tank_id IS NOT DISTINCT FROM n.mother_tank_id
   AND c.father_tank_id IS NOT DISTINCT FROM n.father_tank_id
  WHERE n.rn > 1
)
SELECT * FROM dups;

-- 2) Safely re-point clutches away from duplicate planned_cross_id rows to the canonical
--    (only if doing so will NOT violate uq_clutches_planned_by_date)
WITH moved AS (
  UPDATE public.clutches c
  SET planned_cross_id = d.canonical_id
  FROM pc_dups_map d
  WHERE c.planned_cross_id = d.dup_id
    AND NOT EXISTS (
      SELECT 1
      FROM public.clutches c2
      WHERE c2.planned_cross_id = d.canonical_id
        AND (
              (c.date_birth IS NULL AND c2.date_birth IS NULL) OR
              (c.date_birth IS NOT NULL AND c2.date_birth IS NOT NULL AND c2.date_birth = c.date_birth)
            )
    )
  RETURNING c.id_uuid
)
SELECT COUNT(*) AS re_pointed FROM moved;

-- 3) Delete duplicate planned_cross rows that no longer have dependents
DELETE FROM public.planned_crosses pc
USING pc_dups_map d
WHERE pc.id_uuid = d.dup_id
  AND NOT EXISTS (
    SELECT 1 FROM public.clutches c WHERE c.planned_cross_id = pc.id_uuid
  );

-- 4) Enforce uniqueness going forward (partial unique index)
CREATE UNIQUE INDEX IF NOT EXISTS uq_planned_crosses_clutch_parents
  ON public.planned_crosses (clutch_id, mother_tank_id, father_tank_id)
  WHERE mother_tank_id IS NOT NULL AND father_tank_id IS NOT NULL;

COMMIT;
