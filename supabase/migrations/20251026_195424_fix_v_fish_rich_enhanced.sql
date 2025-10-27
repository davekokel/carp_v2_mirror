BEGIN;
-- Only v_fish_rich changes shape; drop it first to avoid OR REPLACE column conflicts
DROP VIEW IF EXISTS public.v_fish_rich;

CREATE VIEW public.v_fish_rich AS
WITH all_alleles AS (
  SELECT
    fta.fish_uuid,
    fta.transgene_base_code,
    fta.allele_number,
    COALESCE(ta.allele_name, 'gu' || fta.allele_number::int::text)              AS allele_name,
    ('Tg(' || fta.transgene_base_code || ')' || COALESCE(ta.allele_name, 'gu' || fta.allele_number::int::text))
      AS transgene_pretty
  FROM public.fish_transgene_alleles AS fta
  LEFT JOIN public.transgene_alleles   AS ta
    ON  ta.transgene_base_code = fta.transgene_base_code
    AND ta.allele_number       = fta.allele_number
),
rollup AS (
  SELECT
    aa.f_bd.fish_uuid,
    STRING_AGG(aa.transgene_pretty, '; ' ORDER BY aa.transgene_pretty) AS genotype_rollup
  FROM all_alleles AS aa
  GROUP BY aa.fish_uuid
),
first_allele AS (
  SELECT DISTINCT ON (aa.fish_uuid)
    aa.fish_uuid,
    aa.transgene_base_code,
    aa.allele_number,
    (aa.transgene_base_code || '_' || aa.allele_number::int::text)    AS allele_code,
    aa.transgene_pretty                                                AS first_transgene_pretty
  FROM all_alleles AS aa
  ORDER BY aa.fish_uuid, aa.transgene_base_code, aa.allele_number
)
SELECT
  f.fish_uuid,
  f.fish_code,
  f.name                           AS fish_name,
  f.nickname                       AS fish_nickname,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth,
  COALESCE(cnt.current_tanks, 0)::int                                     AS n_active_tanks,
  fa.allele_number,
  fa.allele_code,
  COALESCE(fa.first_transgene_pretty, 'WT(' || COALESCE(f.genetic_background,'') || ')')
                                     AS transgene_pretty,
  COALESCE(r.genotype_rollup,        'WT(' || COALESCE(f.genetic_background,'') || ')')
                                     AS genotype_rollup,
  f.created_at
FROM public.fish                                AS f
LEFT JOIN public.v_fish_current_tank_counts     AS cnt ON cnt.fish_uuid = f.fish_uuid
LEFT JOIN first_allele                          AS fa  ON fa.fish_uuid  = f.fish_uuid
LEFT JOIN rollup                                AS r   ON r.fish_uuid   = f.fish_uuid;
COMMIT;
