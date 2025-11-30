BEGIN;

-- 1) Add structured columns if they don't exist yet
ALTER TABLE public.constructs
  ADD COLUMN IF NOT EXISTS code_prefix text,
  ADD COLUMN IF NOT EXISTS code_number integer,
  ADD COLUMN IF NOT EXISTS code_normalized text;

COMMENT ON COLUMN public.constructs.code_prefix IS
  'Normalized alphanumeric prefix for the construct code (e.g. MGCO, PDQM).';

COMMENT ON COLUMN public.constructs.code_number IS
  'Normalized integer suffix for the construct code (e.g. 1, 4, 117).';

COMMENT ON COLUMN public.constructs.code_normalized IS
  'Canonical normalized code in PREFIX-### form (e.g. MGCO-001, PDQM-117).';

-- 2) Backfill from construct_code/base_code where they match PREFIX + number

WITH src AS (
  SELECT
    id,
    (regexp_matches(
       COALESCE(construct_code, base_code, ''),
       '^([A-Za-z]+)[-_]?0*([0-9]+)$'
     ))[1] AS prefix,
    ((regexp_matches(
       COALESCE(construct_code, base_code, ''),
       '^([A-Za-z]+)[-_]?0*([0-9]+)$'
     ))[2])::int AS num
  FROM public.constructs
  WHERE COALESCE(construct_code, base_code, '') ~ '^[A-Za-z]+[-_]?[0-9]+$'
)
UPDATE public.constructs c
SET
  code_prefix    = UPPER(src.prefix),
  code_number    = src.num,
  code_normalized = UPPER(src.prefix) || '-' || lpad(src.num::text, 3, '0')
FROM src
WHERE c.id = src.id;

-- 3) Unique index on normalized code (only where filled)
CREATE UNIQUE INDEX IF NOT EXISTS uq_constructs_code_normalized
  ON public.constructs(code_normalized)
  WHERE code_normalized IS NOT NULL;

-- 4) Helper view for debugging / future use
DROP VIEW IF EXISTS public.v_construct_codes_normalized CASCADE;

CREATE VIEW public.v_construct_codes_normalized AS
SELECT
  id,
  construct_code,
  base_code,
  code_prefix,
  code_number,
  code_normalized
FROM public.constructs;

COMMENT ON VIEW public.v_construct_codes_normalized IS
  'Constructs with normalized prefix/number and canonical code_normalized.';

COMMIT;
