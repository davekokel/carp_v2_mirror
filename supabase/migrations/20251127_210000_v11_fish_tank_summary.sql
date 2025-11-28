BEGIN;

DROP VIEW IF EXISTS public.v11_fish_tank_summary;

CREATE VIEW public.v11_fish_tank_summary AS
WITH fis AS (
  SELECT
    fish_code,
    birthday,
    genotype_basecode_code,
    genotype_transgene_allele_code,
    treatment_code,
    treatments_and_transgenes,
    all_fluor_tag_rollup,
    all_organelle_fluor_rollup
  FROM public.v11_fish_instance_star
),
tank_counts AS (
  -- use v_tanks_overview, which we know has fish_code
  SELECT
    fish_code::text AS fish_code,
    COUNT(*)::int   AS n_tanks
  FROM public.v_tanks_overview
  GROUP BY fish_code
)
SELECT
  tc.fish_code,
  MAX(f.birthday)                    AS birthday,
  MAX(f.genotype_basecode_code)      AS genotype_basecode_code,
  MAX(f.genotype_transgene_allele_code) AS genotype_transgene_allele_code,
  MAX(f.treatment_code)              AS treatment_code,
  MAX(f.treatments_and_transgenes)   AS treatments_and_transgenes,
  MAX(f.all_fluor_tag_rollup)        AS all_fluor_tag_rollup,
  MAX(f.all_organelle_fluor_rollup)  AS all_organelle_fluor_rollup,
  tc.n_tanks
FROM tank_counts tc
LEFT JOIN fis f ON f.fish_code = tc.fish_code
GROUP BY tc.fish_code, tc.n_tanks;

COMMIT;
