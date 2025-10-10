BEGIN;

-- 1) Find canon/dups for (clutch_id, mother_tank_id, father_tank_id) when both tanks are present
CREATE TEMP TABLE pc_dups_map ON COMMIT DROP AS
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
  WHERE mother_tank_id IS NOT NULL
    AND father_tank_id IS NOT NULL
)
SELECT
  r_keep.id_uuid  AS canonical_id,
  r_dup.id_uuid   AS dup_id
FROM ranked r_keep
JOIN ranked r_dup
  ON r_keep.clutch_id      = r_dup.clutch_id
 AND r_keep.mother_tank_id = r_dup.mother_tank_id
 AND r_keep.father_tank_id = r_dup.father_tank_id
WHERE r_keep.rn = 1 AND r_dup.rn > 1;

-- 2) Repoint clutches → canonical planned_cross, but only where it won't hit uq_clutches_planned_by_date
--    Skip any row that would cause a (planned_cross_id, date_birth) duplicate; we'll leave those dups in place.
WITH cand AS (
  SELECT
    c.id                           AS clutch_row_id,
    c.planned_cross_id             AS dup_pid,
    d.canonical_id,
    c.date_birth
  FROM public.clutches c
  JOIN pc_dups_map d ON d.dup_id = c.planned_cross_id
), safe AS (
  SELECT cand.*
  FROM cand
  WHERE NOT EXISTS (
    SELECT 1
    FROM public.clutches c2
    WHERE c2.id <> cand.clutch_row_id
      AND c2.planned_cross_id = cand.canonical_id
      AND c2.date_birth IS NOT DISTINCT FROM cand.date_birth
  )
)
UPDATE public.clutches c
SET planned_cross_id = s.canonical_id
FROM safe s
WHERE c.id = s.clutch_row_id;

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
