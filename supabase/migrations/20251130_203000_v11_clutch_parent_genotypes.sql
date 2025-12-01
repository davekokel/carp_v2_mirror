BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_parent_genotypes;

CREATE VIEW public.v11_clutch_parent_genotypes AS
SELECT
  c.id                     AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  c.cross_id,
  cp.cross_run_code,
  -- mother
  cp.mother_fish_id,
  cp.mother_fish_code,
  cp.mother_genotype_v11_id,
  cp.mother_genotype_basecodes,
  cp.mother_genotype_pretty,
  -- father
  cp.father_fish_id,
  cp.father_fish_code,
  cp.father_genotype_v11_id,
  cp.father_genotype_basecodes,
  cp.father_genotype_pretty,
  -- clutch-level genotype (primary)
  c.genotype_v11_id,
  gv.genotype_basecodes AS clutch_genotype_basecodes,
  gv.genotype_pretty    AS clutch_genotype_pretty
FROM public.clutches c
LEFT JOIN public.v11_cross_parent_genotypes cp
  ON cp.cross_id = c.cross_id
LEFT JOIN public.genotypes_v11 gv
  ON gv.id = c.genotype_v11_id;

COMMENT ON VIEW public.v11_clutch_parent_genotypes IS
  'v11: clutch-level view showing mother/father fish and genotypes, and the clutch primary genotype.';

COMMIT;
