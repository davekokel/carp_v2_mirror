BEGIN;

-- Cleanup: keep only the most-recent RNA per plasmid
WITH ranked AS (
    SELECT
        id_uuid,
        source_plasmid_id,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY source_plasmid_id
            ORDER BY created_at DESC, id_uuid DESC
        ) AS rn
    FROM public.rnas
    WHERE source_plasmid_id IS NOT NULL
),

to_delete AS (
    SELECT id_uuid FROM ranked
    WHERE rn > 1
)

DELETE FROM public.rnas r
USING to_delete d
WHERE r.id_uuid = d.id_uuid;

-- Constraint: enforce one RNA per plasmid going forward
CREATE UNIQUE INDEX IF NOT EXISTS uq_rnas_one_per_plasmid
ON public.rnas (source_plasmid_id)
WHERE source_plasmid_id IS NOT NULL;

COMMIT;
