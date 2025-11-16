BEGIN;

-- Keep for convenience; harmless if unused
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.annotations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind_code  text NOT NULL UNIQUE,
  label      text NOT NULL,
  value_kind text NOT NULL DEFAULT 'numeric',
  units      text,
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.annotations (kind_code, label, value_kind, units)
VALUES
  ('red_intensity',    'Red intensity',    'numeric', '1–100'),
  ('green_intensity',  'Green intensity',  'numeric', '1–100'),
  ('red_frequency',    'Red frequency',    'numeric', '1–100'),
  ('green_frequency',  'Green frequency',  'numeric', '1–100'),
  ('n_animals',        'Number of animals','numeric', NULL),
  ('notes',            'Notes',            'text',    NULL)
ON CONFLICT (kind_code) DO NOTHING;

-- Build latest-per-kind for treated_clutch without depending on annotation_id/target_type
DROP VIEW IF EXISTS public.v_annotations_latest_group CASCADE;

CREATE VIEW public.v_annotations_latest_group AS
WITH ranked AS (
  SELECT
    ja.target_id,              -- -> treated_clutches.id
    tc.treated_clutch_code,    -- friendly group code
    ja.kind_code,              -- e.g., 'red_intensity'
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
