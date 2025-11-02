BEGIN;

-- Companion view that preserves v_clutch_instances intact
-- and adds a corrected offspring genotype column (semicolon list).
CREATE OR REPLACE VIEW public.v_clutch_instances_plus AS
SELECT
  v.*,
  (
    WITH src AS (
      -- prefer the clutch "pretty" genotype; fall back to table column if present; else empty
      SELECT COALESCE(v.clutch_genotype_pretty, ci.normalized_genotype, '') AS s
    ),
    matches AS (
      -- extract all Tg(...) tokens (case-insensitive), keep their order
      SELECT t.m[1] AS tg, t.ord
      FROM src,
           regexp_matches((SELECT s FROM src), '(?i)tg\([^)]+\)[^;×,]*', 'g') WITH ORDINALITY AS t(m, ord)
    ),
    tokens AS (
      -- de-dup while preserving first-seen order
      SELECT DISTINCT ON (tg) tg, ord
      FROM matches
      ORDER BY tg, ord
    )
    SELECT
      CASE
        WHEN EXISTS (SELECT 1 FROM tokens)
          THEN (SELECT string_agg(tg, '; ' ORDER BY ord) FROM tokens)
        ELSE
          -- no Tg(...) tokens found: normalize common delimiters to '; ' for safety
          regexp_replace(
            regexp_replace((SELECT s FROM src), '\s×\s', '; ', 'g'),
            '\s*,\s*', '; ', 'g'
          )
      END
  ) AS clutch_genotype_codes_semicolon
FROM public.v_clutch_instances v
LEFT JOIN public.clutch_instances ci
  ON ci.clutch_instance_code = v.clutch_code;

COMMIT;
