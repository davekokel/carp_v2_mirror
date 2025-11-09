BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.fluors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_code text UNIQUE NOT NULL,
  fluor_name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_code text UNIQUE NOT NULL,
  tag_name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.rnas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rna_code text UNIQUE NOT NULL,
  nickname text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fusions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_id uuid NOT NULL REFERENCES public.fluors(id),
  tag_id uuid NULL REFERENCES public.tags(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_fusions_fluor_tag_notnull'
  ) THEN
    CREATE UNIQUE INDEX uq_fusions_fluor_tag_notnull
      ON public.fusions(fluor_id, tag_id)
      WHERE tag_id IS NOT NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_fusions_fluor_when_tag_null'
  ) THEN
    CREATE UNIQUE INDEX uq_fusions_fluor_when_tag_null
      ON public.fusions(fluor_id)
      WHERE tag_id IS NULL;
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.join_rna_fusions (
  rna_id uuid NOT NULL REFERENCES public.rnas(id) ON DELETE CASCADE,
  fusion_id uuid NOT NULL REFERENCES public.fusions(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (rna_id, fusion_id)
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='alias_target_kind') THEN
    CREATE TYPE public.alias_target_kind AS ENUM ('fluor','tag','dye','rna','plasmid','fish','tank','cross','clutch_inst','treated_clutch');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.join_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_kind public.alias_target_kind NOT NULL,
  target_id uuid NOT NULL,
  alias text NOT NULL,
  alias_norm text GENERATED ALWAYS AS (lower(btrim(alias))) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (target_kind, target_id, alias_norm)
);

CREATE OR REPLACE VIEW public.v_rnas AS
WITH jf AS (
  SELECT
    j.rna_id,
    f.id AS fusion_id,
    fl.fluor_code,
    tg.tag_code
  FROM public.join_rna_fusions j
  JOIN public.fusions f ON f.id=j.fusion_id
  JOIN public.fluors fl ON fl.id=f.fluor_id
  LEFT JOIN public.tags tg ON tg.id=f.tag_id
),
agg AS (
  SELECT
    rna_id,
    (
      SELECT string_agg(s.fluor_code, ', ' ORDER BY s.fluor_code)
      FROM (SELECT DISTINCT fluor_code FROM jf x WHERE x.rna_id=jf.rna_id) s
    ) AS fluors,
    (
      SELECT COALESCE(string_agg(s.tag_code, ', ' ORDER BY s.tag_code),'')
      FROM (SELECT DISTINCT tag_code FROM jf x WHERE x.rna_id=jf.rna_id AND x.tag_code IS NOT NULL) s
    ) AS tags
  FROM jf
  GROUP BY rna_id
)
SELECT
  r.rna_code,
  r.nickname,
  r.notes,
  COALESCE(agg.fluors,'') AS fluors,
  COALESCE(agg.tags,'')   AS tags,
  r.created_at
FROM public.rnas r
LEFT JOIN agg ON agg.rna_id=r.id;

COMMIT;
