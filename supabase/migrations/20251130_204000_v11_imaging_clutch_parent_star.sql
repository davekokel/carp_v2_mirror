BEGIN;

DROP VIEW IF EXISTS public.v11_imaging_clutch_parent_star;

CREATE VIEW public.v11_imaging_clutch_parent_star AS
SELECT
  icr.clutch_code,
  icr.clutch_date,
  icr.estimated_egg_count,
  icr.membership_id,
  icr.membership_role,
  icr.embryo_count,
  icr.mount_notes,
  icr.membership_created_at,
  icr.plate_code,
  icr.slot_label,
  icr.roi_code,
  icr.roi_index,
  icr.data_path,
  -- clutch-level genotype info
  cs.genotype_v11_basecodes      AS clutch_genotype_basecodes,
  cs.genotype_pretty             AS clutch_genotype_pretty,
  cs.treat_codes,
  cs.treat_basecodes,
  cs.expected_genotype_basecodes,
  -- parent-level genotype info
  cpg.mother_fish_code,
  cpg.mother_genotype_basecodes,
  cpg.mother_genotype_pretty,
  cpg.father_fish_code,
  cpg.father_genotype_basecodes,
  cpg.father_genotype_pretty
FROM public.v_imaging_clutches_rois icr
LEFT JOIN public.clutches c
  ON c.clutch_code = icr.clutch_code
LEFT JOIN public.v11_clutch_star cs
  ON cs.clutch_id = c.id
LEFT JOIN public.v11_clutch_parent_genotypes cpg
  ON cpg.clutch_id = c.id;

COMMENT ON VIEW public.v11_imaging_clutch_parent_star IS
  'v11 imaging star: imaging_clutches_rois enriched with clutch genotypes, treatments, and parent genotypes.';

COMMIT;
