BEGIN;

-- Snapshot current view so we can rebuild it in place without knowing all columns.
CREATE OR REPLACE VIEW public.v_clutch_instances_tmp AS
SELECT * FROM public.v_clutch_instances;

-- Rebuild v_clutch_instances: keep every column identical EXCEPT
-- replace clutch_genotype_codes with a tokenized, semicolon-joined offspring list.
DO $$
DECLARE
  cols text := '';
  replacement text := $r$
(
  WITH src AS (
    -- Prefer v.clutch_genotype_pretty; else ci.normalized_genotype; else ''
    SELECT COALESCE(v.clutch_genotype_pretty, ci.normalized_genotype, '') AS s
  ),
  matches AS (
    -- Extract all Tg(...) tokens (case-insensitive), keep their order
    SELECT t.m[1] AS tg, t.ord
    FROM src,
         regexp_matches((SELECT s FROM src), '(?i)tg\([^)]+\)[^;×,]*', 'g') WITH ORDINALITY AS t(m, ord)
  ),
  tokens AS (
    -- De-dup while preserving first-seen order
    SELECT DISTINCT ON (tg) tg, ord
    FROM matches
    ORDER BY tg, ord
  )
  SELECT
    CASE
      WHEN EXISTS (SELECT 1 FROM tokens)
        THEN (SELECT string_agg(tg, '; ' ORDER BY ord) FROM tokens)
      ELSE
        -- No Tg(...) tokens found: normalize common delimiters to '; ' for safety
        regexp_replace(
          regexp_replace((SELECT s FROM src), '\s×\s', '; ', 'g'),
          '\s*,\s*', '; ', 'g'
        )
    END
) AS clutch_genotype_codes
$r$;
BEGIN
  -- Build a SELECT list that is v.* except for clutch_genotype_codes, which we replace.
  SELECT string_agg(
           CASE
             WHEN column_name = 'clutch_genotype_codes'
               THEN replacement
             ELSE format('v.%I', column_name)
           END,
           ', ' ORDER BY ordinal_position
         )
    INTO cols
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='v_clutch_instances';

  -- Recreate the view, joining clutch_instances only to access normalized_genotype if needed.
  EXECUTE 'CREATE OR REPLACE VIEW public.v_clutch_instances AS
           SELECT ' || cols || '
           FROM public.v_clutch_instances_tmp v
           LEFT JOIN public.clutch_instances ci
             ON ci.clutch_instance_code = v.clutch_code';
END $$;

-- Drop the temporary copy.
DROP VIEW public.v_clutch_instances_tmp;

COMMIT;
