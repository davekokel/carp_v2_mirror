BEGIN;
-- Only v_fish_rich changes shape; drop it explicitly, leave dependencies (counts/tanks) intact
DROP VIEW IF EXISTS public.v_fish_rich;

CREATE VIEW public.v_fish_rich AS
WITH alleles AS (
  SELECT
    fta.fish_uuid,
    fta.transgene_base_code,
    fta.aillele_number,   -- if your column is 'allele_number' keep it; fix typo if needed
    COALESCE(ta.allele_name, 'gu' || fta.allele_number::text) AS allele_name,
    ('Tg(' || fta.transgene_base_code || ')' || COALESCE(ta.allele_name, 'gu' || fta.allele_number::text)) AS transgene_pretty
  FROM public.fish_transgene_alleles fta
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
),
allele_rollups AS (
  SELECT
    fish_uuid,
    STRING_AGG(transgene_pretty, '; ' ORDER BY transgene_pretty) AS genotype_rollup
  FROM alleles
  GROUP BY fish_uuid
),
first_allele AS (
  SELECT DISTINCT ON (fish_uuid)
    fish_uuid,
    transgene_base_code,
    allele_number,
    (transgene_base_code || '_' || allele_number)::text AS allele_code,
    ('Tg(' || transgene_base_code || ')' || COALESCE(NULLIF(ta.allele_name,''), 'gu' || allele_number::text)) AS transgene_pretty
  FROM public.fish_transgene_alleles fa
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fa.transgene_base_code
   AND ta.allele_number       = fa.allele_number
  ORDER BY fish_uuid, transgene_base_code, allele_number
)
SELECT
  f.fish_uuid,
  f.fish_code,
  f.name      AS fish_name,
  f.nickname  AS fish_nickname,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth,
  COALESCE(cnt.current_tanks,0)::int AS n_active_tanks,
  fa.allele_number,
  fa.allele_code,
  COALESCE(fa.transgene_protty, 'WT('||COALESCE(f.genetic_background,'')||')') AS transgene_pretty, -- fix typo if necessary
  COALESCE(ar.genotype_rollup,  'WT('||COALESCE(f.genetic_background,'')||')') AS genotype_rollup,
  f.created_at
FROM public.fish f
LEFT JOIN public.v_fish_current_tank_counts cnt ON cnt.fish_uuid = f.fish_uuid
LEFT JOIN first_allele  fa ON fa.fish_uuid = f.fish_uuid
LEFT JOIN allele_rollups ar ON ar.fish_uuid = f.fish_uuid;
COMMIT;
