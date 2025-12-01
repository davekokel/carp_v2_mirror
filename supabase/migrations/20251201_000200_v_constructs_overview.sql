BEGIN;

CREATE OR REPLACE VIEW public.v_constructs_overview AS
WITH base AS (
  SELECT
    c.id,
    c.construct_code,
    c.construct_kind,
    c.construct_name,
    c.resistance,
    COALESCE(c.plasmid_notes, c.description, '') AS description,
    c.created_at
  FROM public.constructs c
),
fusion_join AS (
  SELECT
    cf.construct_id,
    COUNT(DISTINCT cf.fusion_id) AS n_fusions,
    COALESCE(
      string_agg(
        DISTINCT
          CASE
            WHEN fl.fluor_code IS NULL THEN NULL
            ELSE fl.fluor_code
                 || '::'
                 || COALESCE(t.tag_code, '')
                 || '('
                 || COALESCE(f.tag_pos, '')
                 || ')'
          END,
        '||'
      ),
      ''
    ) AS fusion_pretty,
    COALESCE(
      string_agg(
        DISTINCT
          CASE
            WHEN fl.fluor_code IS NULL THEN NULL
            ELSE COALESCE(t.localization, '')
                 || ':'
                 || fl.fluor_code
          END,
        '||'
      ),
      ''
    ) AS organelle_fluors
  FROM public.construct_fusions cf
  JOIN public.fusions f      ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags   t  ON t.id = f.tag_id
  GROUP BY cf.construct_id
)
SELECT
  b.construct_code,
  b.construct_kind,
  b.construct_name,
  b.resistance,
  b.description,
  COALESCE(fj.n_fusions, 0)        AS n_fusions,
  COALESCE(fj.fusion_pretty, '')   AS fusion_pretty,
  COALESCE(fj.organelle_fluors, '') AS organelle_fluors,
  b.created_at
FROM base b
LEFT JOIN fusion_join fj
  ON fj.construct_id = b.id;

COMMENT ON VIEW public.v_constructs_overview IS
  'Constructs with marker rollups: n_fusions, fusion_pretty (fluor::tag(tag_pos)), organelle_fluors (localization:fluor).';

COMMIT;
