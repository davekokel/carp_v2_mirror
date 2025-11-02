BEGIN;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.annotations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind_code  text        NOT NULL UNIQUE,
  label      text        NOT NULL,
  value_type text        NOT NULL CHECK (value_type IN ('number','text')),
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.annotations (kind_code,label,value_type) VALUES
  ('green_intensity','Green intensity','number'),
  ('red_intensity','Red intensity','number'),
  ('green_frequency','Green fraction','number'),
  ('red_frequency','Red fraction','number'),
  ('n_animals','N animals','number'),
  ('health','Health','text'),
  ('notes','Notes','text')
ON CONFLICT (kind_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.join_annotations (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  target_type   text        NOT NULL,
  target_id     uuid        NOT NULL,
  annotation_id uuid        NOT NULL REFERENCES public.annotations(id) ON UPDATE CASCADE ON DELETE CASCADE,
  value_num     numeric,
  value_text    text,
  created_by    text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ja_value_chk CHECK (value_num IS NOT NULL OR value_text IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS ix_join_annotations_target ON public.join_annotations (target_type,target_id,created_at DESC);
CREATE INDEX IF NOT EXISTS ix_join_annotations_ann ON public.join_annotations (annotation_id,created_at DESC);

CREATE OR REPLACE VIEW public.v_annotations_latest AS
WITH ranked AS (
  SELECT
    ja.target_type,
    ja.target_id,
    ja.annotation_id,
    a.kind_code,
    a.label,
    a.value_type,
    ja.value_num,
    ja.value_text,
    ja.created_by,
    ja.created_at,
    ROW_NUMBER() OVER (
      PARTITION BY ja.target_type, ja.target_id, ja.annotation_id
      ORDER BY ja.created_at DESC, ja.id DESC
    ) AS rn
  FROM public.join_annotations ja
  JOIN public.annotations a ON a.id = ja.annotation_id
)
SELECT
  target_type,
  target_id,
  annotation_id,
  kind_code,
  label,
  value_type,
  value_num,
  value_text,
  created_by,
  created_at
FROM ranked
WHERE rn = 1;

CREATE OR REPLACE VIEW public.v_clutch_annotations AS
SELECT
  ci.clutch_instance_code AS clutch_code,
  va.target_id            AS clutch_instance_id,
  va.kind_code            AS kind_code,
  va.label                AS label,
  va.value_type           AS value_type,
  va.value_num,
  va.value_text,
  va.created_at,
  va.created_by
FROM public.v_annotations_latest va
JOIN public.clutch_instances ci ON ci.id = va.target_id
WHERE va.target_type = 'clutch';

CREATE OR REPLACE VIEW public.v_clutch_annotations_pivot AS
WITH va AS (
  SELECT
    ci.clutch_instance_code AS clutch_code,
    va.kind_code,
    va.value_num,
    va.value_text,
    va.created_at
  FROM public.v_annotations_latest va
  JOIN public.clutch_instances ci ON ci.id = va.target_id
  WHERE va.target_type = 'clutch'
)
SELECT
  v.clutch_code,
  MAX(CASE WHEN v.kind_code='green_intensity' THEN v.value_num END) AS green_intensity,
  MAX(CASE WHEN v.kind_code='red_intensity'   THEN v.value_num END) AS red_intensity,
  MAX(CASE WHEN v.kind_code='green_frequency' THEN v.value_num END) AS green_frequency,
  MAX(CASE WHEN v.kind_code='red_frequency'   THEN v.value_num END) AS red_frequency,
  MAX(CASE WHEN v.kind_code='n_animals'       THEN v.value_num END) AS n_animals,
  MAX(CASE WHEN v.kind_code='health'          THEN v.value_text END) AS health,
  MAX(CASE WHEN v.kind_code='notes'           THEN v.value_text END) AS notes,
  MAX(v.created_at) AS annotations_last_at
FROM va v
GROUP BY v.clutch_code;

COMMIT;
