BEGIN;

-- Build a durable mapping of duplicate → canonical concepts
CREATE TEMP TABLE dups_tmp ON COMMIT DROP AS
WITH norm AS (
  SELECT
    id_uuid,
    upper(trim(mother_code)) AS mom,
    upper(trim(father_code)) AS dad,
    created_at,
    row_number() OVER (
      PARTITION BY upper(trim(mother_code)), upper(trim(father_code))
      ORDER BY created_at ASC, id_uuid ASC
    ) AS rn
  FROM public.crosses
),
canon AS (
  SELECT id_uuid AS canonical_id, mom, dad
  FROM norm
  WHERE rn = 1
),
dups AS (
  SELECT n.id_uuid AS dup_id, c.canonical_id
  FROM norm n
  JOIN canon c ON c.mom = n.mom AND c.dad = n.dad
  WHERE n.rn > 1
)
SELECT * FROM dups;

-- 2) Repoint runs and clutches from duplicate concepts → canonical
UPDATE public.cross_instances ci
SET cross_id = d.canonical_id
FROM dups_tmp d
WHERE ci.cross_id = d.dup_id;

UPDATE public.clutches cl
SET cross_id = d.canonical_id
FROM dups_tmp d
WHERE cl.cross_id = d.dup_id;

-- 3) Delete duplicate concept rows (that no longer have dependents)
DELETE FROM public.crosses x
WHERE x.id_uuid IN (SELECT dup_id FROM dups_tmp);

-- 4) Add a case-insensitive uniqueness to prevent re-duplication going forward
CREATE UNIQUE INDEX IF NOT EXISTS uq_crosses_concept_pair
  ON public.crosses (upper(trim(mother_code)), upper(trim(father_code)));

COMMIT;
