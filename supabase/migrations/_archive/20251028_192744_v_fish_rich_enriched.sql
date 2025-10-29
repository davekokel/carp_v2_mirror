-- Enrich v_fish_rich with names (legacy + modern), allele details, genotype rollup,
-- and active tank counts from v_tanks. Idempotent and tolerant of legacy columns.

CREATE OR REPLACE VIEW public.v_fish_rich AS
WITH tcounts AS (
  SELECT v.fish_code::text AS fish_code, COUNT(*)::int AS n_active_tanks
  FROM public.v_tanks v
  WHERE v.status = 'active'
  GROUP BY v.fish_code
),
alleles AS (
  SELECT
    f.fish_uuid,
    f.fish_code::text                         AS fish_code,
    fta.transgene_base_code                   AS transgene_base_code,
    fta.allele_number                         AS allele_number,
    ta.allele_nickname::text                  AS allele_nickname,
    ('gu' || fta.allele_number::text)         AS allele_code,
    ('Tg(' || fta.transgene_base_code || ')' ||
      ('gu' || fta.allele_number::text))      AS transgene_pretty
  FROM public.fish f
  LEFT JOIN public.fish_transgene_alleles fta
    ON fta.fish_uuid = f.fish_uuid
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
),
geno AS (
  SELECT
    a.fish_uuid,
    string_agg(a.transgene_pretty, '; ' ORDER BY a.transgene_pretty)::text AS genotype_rollup
  FROM alleles a
  GROUP BY a.fish_uuid
)
SELECT
  f.fish_uuid::uuid                           AS fish_uuid,
  f.fish_code::text                           AS fish_code,
  COALESCE(f.fish_name, f.name, '')::text     AS fish_name,
  COALESCE(f.fish_nickname, f.nickname, '')::text AS fish_nickname,
  f.genetic_background::text                  AS genetic_background,
  f.line_building_stage::text                 AS line_building_stage,
  f.date_birth::date                          AS date_birth,
  COALESCE(a.allele_number, 0)::int           AS allele_number,
  COALESCE(a.allele_code, '')::text           AS allele_code,
  COALESCE(tc.n_active_tanks, 0)::int         AS n_active_tanks,
  COALESCE(a.transgene_pretty, '')::text      AS transgene_pretty,
  COALESCE(g.genotype_rollup, '')::text       AS genotype_rollup,
  f.created_at::timestamptz                   AS created_at
FROM public.fish f
LEFT JOIN alleles a  ON a.fish_uuid = f.fish_uuid
LEFT JOIN tcounts tc ON tc.fish_code = f.fish_code
LEFT JOIN geno g     ON g.fish_uuid = f.fish_uuid
ORDER BY f.fish_code, a.transgene_pretty NULLS LAST;
