BEGIN;

-- 1) Canonical per (mother_code, father_code) ignoring case/whitespace
WITH norm AS (
    SELECT
        id_uuid,
        created_at,
        upper(trim(mother_code)) AS mom,
        upper(trim(father_code)) AS dad,
        row_number() OVER (
            PARTITION BY upper(trim(mother_code)), upper(trim(father_code))
            ORDER BY created_at ASC, id_uuid ASC
        ) AS rn
    FROM public.crosses
),

canon AS (
    SELECT
        id_uuid AS canonical_id,
        mom,
        dad
    FROM norm
    WHERE rn = 1
),

dups AS (
    SELECT
        n.id_uuid AS dup_id,
        c.canonical_id
    FROM norm AS n
    INNER JOIN canon AS c ON n.mom = c.mom AND n.dad = c.dad
    WHERE n.rn > 1
)

-- 2) Repoint runs and clutches from duplicate concepts → canonical
UPDATE public.cross_instances ci
SET cross_id = d.canonical_id
FROM dups AS d
WHERE ci.cross_id = d.dup_id;

UPDATE public.clutches cl
SET cross_id = d.canonical_id
FROM dups AS d
WHERE cl.cross_id = d.dup_id;

-- 3) Delete duplicate concept rows (that no longer have dependents)
DELETE FROM public.crosses x
USING dups d
WHERE x.id_uuid = d.dup_id;

-- 4) Add a case-insensitive uniqueness to prevent re-duplication going forward
CREATE UNIQUE INDEX IF NOT EXISTS uq_crosses_concept_pair
ON public.crosses (upper(trim(mother_code)), upper(trim(father_code)));

COMMIT;
