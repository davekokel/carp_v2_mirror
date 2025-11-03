BEGIN;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.annotations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind_code text NOT NULL,
  label text NOT NULL,
  value_type text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_annotations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_type text NOT NULL,
  target_id uuid NOT NULL,
  annotation_id uuid NOT NULL,
  value_num numeric,
  value_text text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_join_annotations_target ON public.join_annotations (target_type, target_id);
CREATE INDEX IF NOT EXISTS ix_join_annotations_ann ON public.join_annotations (annotation_id);

DROP VIEW IF EXISTS public.v_clutch_annotations_pivot;
DROP VIEW IF EXISTS public.v_clutch_annotations;

CREATE VIEW public.v_clutch_annotations AS
WITH ranked AS (
  SELECT
    c.id AS clutch_id,
    a.id AS annotation_id,
    a.kind_code,
    a.label,
    a.value_type,
    ja.value_num,
    ja.value_text,
    ja.created_at,
    ROW_NUMBER() OVER (
      PARTITION BY c.id, a.id
      ORDER BY ja.created_at DESC, ja.id DESC
    ) AS rn
  FROM public.join_annotations ja
  JOIN public.annotations a
    ON a.id = ja.annotation_id
  JOIN public.clutches c
    ON lower(ja.target_type) IN ('clutch','clutches')
   AND ja.target_id = c.id
)
SELECT
  clutch_id,
  annotation_id,
  kind_code,
  label,
  value_type,
  value_num,
  value_text,
  created_at
FROM ranked
WHERE rn = 1;

CREATE VIEW public.v_clutch_annotations_pivot AS
SELECT
  clutch_id,
  jsonb_object_agg(
    kind_code,
    CASE
      WHEN value_type IN ('num','number','float','int','integer') THEN to_jsonb(value_num)
      ELSE to_jsonb(value_text)
    END
  ) AS annotations_json
FROM public.v_clutch_annotations
GROUP BY clutch_id;

COMMIT;
