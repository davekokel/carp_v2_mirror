BEGIN;

DROP VIEW IF EXISTS public.v11_cross_parent_genotypes;

CREATE VIEW public.v11_cross_parent_genotypes AS
SELECT
  x.id                      AS cross_id,
  x.cross_run_code,
  x.cross_date,
  -- mother
  x.female_fish_id          AS mother_fish_id,
  fm.fish_code              AS mother_fish_code,
  fms.genotype_v11_id       AS mother_genotype_v11_id,
  fms.genotype_basecodes    AS mother_genotype_basecodes,
  fms.genotype_pretty       AS mother_genotype_pretty,
  -- father
  x.male_fish_id            AS father_fish_id,
  mm.fish_code              AS father_fish_code,
  ffs.genotype_v11_id       AS father_genotype_v11_id,
  ffs.genotype_basecodes    AS father_genotype_basecodes,
  ffs.genotype_pretty       AS father_genotype_pretty,
  -- legacy expected genotype label, canonical v11 genotype if present
  x.legacy_expected_genotype_code,
  gv.genotype_basecodes     AS cross_genotype_basecodes,
  gv.genotype_pretty        AS cross_genotype_pretty
FROM public.crosses x
LEFT JOIN public.fish_instances_v10 fm
  ON fm.id = x.female_fish_id
LEFT JOIN public.v11_fish_instance_star fms
  ON fms.fish_instance_id = fm.id
LEFT JOIN public.fish_instances_v10 mm
  ON mm.id = x.male_fish_id
LEFT JOIN public.v11_fish_instance_star ffs
  ON ffs.fish_instance_id = mm.id
LEFT JOIN public.genotypes_v11 gv
  ON gv.id = x.genotype_v11_id;

COMMENT ON VIEW public.v11_cross_parent_genotypes IS
  'v11: cross-level view showing mother/father fish codes and genotypes, plus any cross-level expected genotype.';

COMMIT;
