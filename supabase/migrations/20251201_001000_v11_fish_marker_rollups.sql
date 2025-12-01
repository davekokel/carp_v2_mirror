BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_marker_rollups AS
WITH base AS (
  SELECT
    fi.id         AS fish_instance_id,
    c.id          AS construct_id
  FROM public.fish_instances_v10 fi
  LEFT JOIN public.fish_transgene_alleles fta
    ON fta.fish_id = fi.id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
  LEFT JOIN public.constructs c
    ON c.base_code = ta.transgene_base_code
),
with_markers AS (
  SELECT
    b.fish_instance_id,
    b.construct_id,
    cf.fusion_id,
    f.id            AS fusion_pk,
    flr.fluor_code,
    t.tag_code,
    t.localization,
    f.tag_pos
  FROM base b
  LEFT JOIN public.construct_fusions cf
    ON cf.construct_id = b.construct_id
  LEFT JOIN public.fusions f
    ON f.id = cf.fusion_id
  LEFT JOIN public.fluors flr
    ON flr.id = f.fluor_id
  LEFT JOIN public.tags t
    ON t.id = f.tag_id
)
SELECT
  fish_instance_id,
  COUNT(DISTINCT construct_id) AS n_constructs,
  COUNT(DISTINCT fluor_code)   AS n_fluors,
  COALESCE(
    string_agg(
      DISTINCT
        CASE
          WHEN fluor_code IS NULL THEN NULL
          ELSE fluor_code
               || '::'
               || COALESCE(tag_code, '')
               || '('
               || COALESCE(tag_pos, '')
               || ')'
        END,
      '||'
    ),
    ''
  ) AS fluor_tag_rollup,
  COALESCE(
    string_agg(
      DISTINCT
        CASE
          WHEN fluor_code IS NULL THEN NULL
          ELSE COALESCE(localization, '')
               || ':'
               || fluor_code
        END,
      '||'
    ),
    ''
  ) AS organelle_fluor_rollup
FROM with_markers
GROUP BY fish_instance_id
ORDER BY fish_instance_id;

COMMENT ON VIEW public.v11_fish_marker_rollups IS
  'v11: per fish_instance marker rollups: n_constructs, n_fluors, fluor_tag_rollup (fluor::tag(tag_pos)), organelle_fluor_rollup (localization:fluor).';

COMMIT;
