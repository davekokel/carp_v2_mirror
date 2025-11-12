BEGIN;

-- UUIDs (usually already enabled in Supabase)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Base catalog of annotation kinds
CREATE TABLE IF NOT EXISTS public.annotations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind_code  text NOT NULL UNIQUE,       -- stable code you reference from app
  label      text NOT NULL,              -- human-friendly label
  value_kind text NOT NULL DEFAULT 'numeric',  -- 'numeric' | 'text' | 'bool'
  units      text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Seed the kinds this page writes/reads
INSERT INTO public.annotations (kind_code, label, value_kind, units)
VALUES
  ('red_intensity',    'Red intensity',    'numeric', '1–100'),
  ('green_intensity',  'Green intensity',  'numeric', '1–100'),
  ('red_frequency',    'Red frequency',    'numeric', '1–100'),
  ('green_frequency',  'Green frequency',  'numeric', '1–100'),
  ('n_animals',        'Number of animals','numeric', NULL),
  ('notes',            'Notes',            'text',    NULL)
ON CONFLICT (kind_code) DO NOTHING;

-- Optional helper: latest values per treated group (by kind)
-- The annotate page will use this if present; harmless otherwise.
CREATE OR REPLACE VIEW public.v_annotations_latest_group AS
WITH ranked AS (
  SELECT
    ja.target_id,
    a.kind_code,
    ja.value_num,
    ja.value_text,
    ja.created_at,
    ROW_NUMBER() OVER (PARTITION BY ja.target_id, a.kind_code
                       ORDER BY ja.created_at DESC NULLS LAST) AS rn
  FROM public.join_annotations ja
  JOIN public.annotations a ON a.id = ja.annotation_id
  WHERE ja.target_type = 'treated_clutch'
)
SELECT *
FROM ranked
WHERE rn = 1;

COMMIT;
