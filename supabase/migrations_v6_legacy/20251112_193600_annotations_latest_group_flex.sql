BEGIN;

DROP VIEW IF EXISTS public.v_annotations_latest_group;

-- Build latest-per-kind, per treated group
CREATE VIEW public.v_annotations_latest_group AS
WITH ranked AS (
  SELECT
    ja.target_id,                        -- UUID of treated_clutches.id
    tc.treated_clutch_code,             -- friendly group code
    ja.kind_code,                       -- e.g., 'red_intensity'
    ja.value_num,
    ja.value_text,
    ja.created_at,
    ROW_NUMBER() OVER (
      PARTITION BY ja.target_id, ja.kind_code
      ORDER BY ja.created_at DESC NULLS LAST
    ) AS rn
  FROM public.join_annotations ja
  JOIN public.treated_clutches tc ON tc.id = ja.target_id
  WHERE ja.target_kind = 'treated_clutch'
)
SELECT *
FROM ranked
WHERE rn = 1;

COMMIT;
