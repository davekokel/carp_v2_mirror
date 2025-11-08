BEGIN;

-- Latest annotation rows per treated_clutch + kind
DROP VIEW IF EXISTS public.v_annotations_latest_group;
CREATE VIEW public.v_annotations_latest_group AS
WITH ranked AS (
  SELECT
    ja.target_id::uuid          AS treated_clutch_id,
    a.kind_code,
    ja.value_num,
    ja.value_text,
    ja.created_by,
    ja.created_at,
    ROW_NUMBER() OVER (
      PARTITION BY ja.target_id, a.kind_code
      ORDER BY ja.created_at DESC, ja.id DESC
    ) AS rn
  FROM public.join_annotations ja
  JOIN public.annotations a ON a.id = ja.annotation_id
  WHERE ja.target_type = 'treated_clutch'
)
SELECT * FROM ranked WHERE rn = 1;

-- Pivot-style rollup: one row per treated_clutch_code
DROP VIEW IF EXISTS public.v_treated_clutch_annotations_pivot;
CREATE VIEW public.v_treated_clutch_annotations_pivot AS
WITH base AS (
  SELECT
    tc.treated_clutch_code,
    l.kind_code,
    l.value_num,
    l.value_text,
    l.created_by,
    l.created_at
  FROM public.treated_clutches tc
  LEFT JOIN public.v_annotations_latest_group l
    ON l.treated_clutch_id = tc.id
)
SELECT
  treated_clutch_code,
  MAX(CASE WHEN kind_code='red_intensity'     THEN value_num END)  AS red_intensity,
  MAX(CASE WHEN kind_code='green_intensity'   THEN value_num END)  AS green_intensity,
  MAX(CASE WHEN kind_code='green_frequency'   THEN value_num END)  AS green_frequency,
  MAX(CASE WHEN kind_code='red_frequency'     THEN value_num END)  AS red_frequency,
  MAX(CASE WHEN kind_code='n_animals'         THEN value_num END)  AS n_animals,
  MAX(CASE WHEN kind_code='notes'             THEN value_text END) AS notes,
  MAX(created_by)   AS annotated_by,
  MAX(created_at)   AS annotated_at
FROM base
GROUP BY treated_clutch_code;

COMMIT;
