BEGIN;

-- Recreate both views in dependency order:
-- 1) Drop the dependent pivot
DROP VIEW IF EXISTS public.v_treated_clutch_annotations_pivot;

-- 2) Recreate v_annotations_latest_group (base view)
DROP VIEW IF EXISTS public.v_annotations_latest_group;
CREATE VIEW public.v_annotations_latest_group AS
WITH ranked AS (
  SELECT
    j.target_type,
    j.target_id,
    a.kind_code,
    COALESCE(j.value_num,  0::numeric) AS value_num,
    COALESCE(j.value_text, ''::text)   AS value_text,
    j.created_at,
    ROW_NUMBER() OVER (
      PARTITION BY j.target_type, j.target_id, a.kind_code
      ORDER BY j.created_at DESC NULLS LAST, j.id DESC
    ) AS rn
  FROM public.join_annotations j
  JOIN public.annotations a
    ON a.id = j.annotation_id
  WHERE j.target_type IN ('clutch','treated_clutch')  -- extend as needed
)
SELECT
  target_type,
  target_id,
  kind_code,
  value_num,
  value_text,
  created_at
FROM ranked
WHERE rn = 1;

-- 3) Recreate pivot (depends on latest_group)
CREATE VIEW public.v_treated_clutch_annotations_pivot AS
SELECT
  tg.id::uuid       AS treated_clutch_id,
  tg.treated_clutch_code,
  MAX(CASE WHEN g.kind_code='red_intensity'   THEN g.value_num  END) AS red_intensity,
  MAX(CASE WHEN g.kind_code='green_intensity' THEN g.value_num  END) AS green_intensity,
  MAX(CASE WHEN g.kind_code='green_frequency' THEN g.value_num  END) AS green_frequency,
  MAX(CASE WHEN g.kind_code='red_frequency'   THEN g.value_num  END) AS red_frequency,
  MAX(CASE WHEN g.kind_code='n_animals'       THEN g.value_num  END) AS n_animals,
  MAX(CASE WHEN g.kind_code='notes'           THEN g.value_text END) AS notes,
  MAX(g.created_at) AS annotations_last_at
FROM public.treated_clutches tg
LEFT JOIN public.v_annotations_latest_group g
  ON g.target_type = 'treated_clutch'
 AND g.target_id   = tg.id
GROUP BY tg.id, tg.treated_clutch_code;

COMMIT;
