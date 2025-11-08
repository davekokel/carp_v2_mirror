BEGIN;

-- 0) tables -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.annotations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind_code   text NOT NULL UNIQUE,
  label       text,
  description text
);

CREATE TABLE IF NOT EXISTS public.join_annotations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_type   text NOT NULL,             -- e.g. 'clutch', 'treated_clutch', 'fish', 'tank', ...
  target_id     uuid NOT NULL,             -- UUID of the target row
  annotation_id uuid NOT NULL REFERENCES public.annotations(id) ON DELETE CASCADE,
  value_num     numeric,
  value_text    text,
  created_by    text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS ix_join_annotations_target
  ON public.join_annotations (target_type, target_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_join_annotations_annotation
  ON public.join_annotations (annotation_id);

-- 1) seed common kinds (no duplicates) ---------------------------------------
INSERT INTO public.annotations (kind_code, label, description)
VALUES
  ('red_intensity','Red intensity','0..1'),
  ('green_intensity','Green intensity','0..1'),
  ('red_frequency','Red frequency','0..1'),
  ('green_frequency','Green frequency','0..1'),
  ('n_animals','N animals','Count of animals'),
  ('notes','Notes','Free text')
ON CONFLICT (kind_code) DO NOTHING;

-- 2) "latest" views (clutch + treated_clutch) --------------------------------
DROP VIEW IF EXISTS public.v_annotations_latest;
CREATE VIEW public.v_annotations_latest AS
WITH ranked AS (
  SELECT
    ja.target_type,
    ja.target_id,
    a.kind_code,
    ja.value_num,
    ja.value_text,
    ja.created_by,
    ja.created_at,
    ROW_NUMBER() OVER (
      PARTITION BY ja.target_type, ja.target_id, a.kind_code
      ORDER BY ja.created_at DESC, ja.id DESC
    ) AS rn
  FROM public.join_annotations ja
  JOIN public.annotations a ON a.id = ja.annotation_id
)
SELECT * FROM ranked WHERE rn = 1;

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

-- 3) Per-treated-group pivot --------------------------------------------------
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
  MAX(CASE WHEN kind_code='red_intensity'     THEN value_num  END) AS red_intensity,
  MAX(CASE WHEN kind_code='green_intensity'   THEN value_num  END) AS green_intensity,
  MAX(CASE WHEN kind_code='green_frequency'   THEN value_num  END) AS green_frequency,
  MAX(CASE WHEN kind_code='red_frequency'     THEN value_num  END) AS red_frequency,
  MAX(CASE WHEN kind_code='n_animals'         THEN value_num  END) AS n_animals,
  MAX(CASE WHEN kind_code='notes'             THEN value_text END) AS notes,
  MAX(created_by)  AS annotated_by,
  MAX(created_at)  AS annotated_at
FROM base
GROUP BY treated_clutch_code;

-- 4) Backfill clutch → baseline treated_clutch (T(CI)-0) ---------------------
--    Copy rows only when an equivalent treated_clutch annotation is not present
WITH src AS (
  SELECT
    ja.id             AS ja_id,
    ja.target_id      AS clutch_uuid,
    ja.annotation_id,
    ja.value_num,
    ja.value_text,
    ja.created_by,
    ja.created_at,
    tc.id             AS treated_clutch_id
  FROM public.join_annotations ja
  JOIN public.clutch_instances ci
    ON ci.id = ja.target_id
  JOIN public.treated_clutches tc
    ON tc.clutch_instance_id = ci.id
   AND tc.treated_clutch_code = 'T('||ci.clutch_instance_code||')-0'
  WHERE ja.target_type = 'clutch'
),
dupe_check AS (
  SELECT s.*
  FROM src s
  LEFT JOIN public.join_annotations j2
    ON j2.target_type   = 'treated_clutch'
   AND j2.target_id     = s.treated_clutch_id
   AND j2.annotation_id = s.annotation_id
   AND COALESCE(j2.value_num,  0) = COALESCE(s.value_num,  0)
   AND COALESCE(j2.value_text,'') = COALESCE(s.value_text,'')
  WHERE j2.id IS NULL
)
INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, value_text, created_by, created_at)
SELECT
  'treated_clutch',
  treated_clutch_id,
  annotation_id,
  value_num,
  value_text,
  created_by,
  created_at
FROM dupe_check;

COMMIT;
