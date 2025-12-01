BEGIN;

-- 1) Drop dependent views in dependency order
DROP VIEW IF EXISTS public.v11_imaging_clutch_parent_star;
DROP VIEW IF EXISTS public.v11_clutch_parent_genotypes;
DROP VIEW IF EXISTS public.v11_cross_parent_genotypes;
DROP VIEW IF EXISTS public.v11_fish_instance_star;

-- 2) Recreate v11_fish_instance_star with instance_stage
CREATE VIEW public.v11_fish_instance_star AS
WITH fish_core AS (
  SELECT
    fi.id               AS fish_instance_id,
    fi.fish_code,
    fi.line_id,
    fi.birthday,
    fi.instance_stage,
    fi.genotype_v11_id  AS fish_genotype_v11_id
  FROM public.fish_instances_v10 fi
),
line_info AS (
  SELECT
    fl.id               AS line_id,
    fl.line_code,
    fl.nickname         AS line_nickname,
    fl.genetic_background,
    fl.construct_code   AS line_construct_code
  FROM public.fish_lines fl
),
alleles AS (
  SELECT
    fa.fish_instance_id,
    fa.allele_canonical_rollup,
    fa.allele_label_rollup
  FROM public.v11_fish_allele_rollups fa
),
constructs AS (
  SELECT
    cr.fish_instance_id,
    cr.genotype_basecodes
  FROM public.v11_fish_construct_rollups cr
),
genos AS (
  SELECT
    g.id,
    g.genotype_code,
    g.genotype_basecodes,
    g.genotype_pretty
  FROM public.genotypes_v11 g
)
SELECT
  fc.fish_instance_id,
  fc.fish_code,
  fc.birthday,
  fc.instance_stage,
  li.line_code,
  li.line_nickname,
  li.genetic_background,
  li.line_construct_code,
  al.allele_canonical_rollup,
  al.allele_label_rollup,
  c.genotype_basecodes,
  COALESCE(fc.fish_genotype_v11_id, g.id) AS genotype_v11_id,
  g.genotype_code,
  g.genotype_pretty
FROM fish_core fc
LEFT JOIN line_info li
  ON li.line_id = fc.line_id
LEFT JOIN alleles al
  ON al.fish_instance_id = fc.fish_instance_id
LEFT JOIN constructs c
  ON c.fish_instance_id = fc.fish_instance_id
LEFT JOIN genos g
  ON g.genotype_basecodes = c.genotype_basecodes;

COMMENT ON VIEW public.v11_fish_instance_star IS
  'v11 fish instance star: fish_code, birthday, instance_stage, line info, allele rollups, construct-based genotype and canonical v11 genotype.';

-- 3) Recreate v11_cross_parent_genotypes using updated fish_instance_star
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

-- 4) Recreate v11_clutch_parent_genotypes
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

-- 5) Recreate v11_imaging_clutch_parent_star
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
