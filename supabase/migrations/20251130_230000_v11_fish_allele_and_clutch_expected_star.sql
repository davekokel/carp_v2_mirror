BEGIN;

------------------------------------------------------------
-- 1) v11_fish_allele_star
--    fish + line + stage + birthday + allele rollups
------------------------------------------------------------

DROP VIEW IF EXISTS public.v11_fish_allele_star;

CREATE VIEW public.v11_fish_allele_star AS
SELECT
  fi.id                  AS fish_instance_id,
  fi.fish_code,
  fi.birthday,
  fi.instance_stage,
  fl.line_code,
  fl.nickname            AS line_nickname,
  fl.genetic_background,
  fa.allele_canonical_rollup,
  fa.allele_label_rollup
FROM public.fish_instances_v10 fi
LEFT JOIN public.fish_lines fl
  ON fl.id = fi.line_id
LEFT JOIN public.v11_fish_allele_rollups fa
  ON fa.fish_instance_id = fi.id;

COMMENT ON VIEW public.v11_fish_allele_star IS
  'v11 fish allele star: one row per fish_instance with fish_code, stage, birthday, line info, and allele rollups.';

------------------------------------------------------------
-- 2) genotypes_v11.source_system
--    separate legacy LCL vs v11-style genotypes
------------------------------------------------------------

ALTER TABLE public.genotypes_v11
  ADD COLUMN IF NOT EXISTS source_system text;

COMMENT ON COLUMN public.genotypes_v11.source_system IS
  'Origin of this genotype definition (e.g. legacy_clutch_v9, v11_fish_from_constructs, v11_child_from_parents, etc.).';

-- Backfill a coarse classification:
--  - legacy_clutch_v9: genotype_basecodes starting with LCL-
--  - v11_construct_rollup: everything else (for now)
UPDATE public.genotypes_v11
SET source_system = 'legacy_clutch_v9'
WHERE source_system IS NULL
  AND genotype_basecodes ILIKE 'LCL-%';

UPDATE public.genotypes_v11
SET source_system = 'v11_construct_rollup'
WHERE source_system IS NULL;

------------------------------------------------------------
-- 3) v11_clutch_expected_genotype_star
--    parent-based possible genotypes + treatments
------------------------------------------------------------

DROP VIEW IF EXISTS public.v11_clutch_expected_genotype_star;

CREATE VIEW public.v11_clutch_expected_genotype_star AS
SELECT
  c.id                           AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  c.cross_id,
  -- parent info
  cpg.mother_fish_id,
  cpg.mother_fish_code,
  cpg.mother_genotype_v11_id,
  cpg.mother_genotype_basecodes,
  cpg.mother_genotype_pretty,
  cpg.father_fish_id,
  cpg.father_fish_code,
  cpg.father_genotype_v11_id,
  cpg.father_genotype_basecodes,
  cpg.father_genotype_pretty,
  -- clutch primary genotype (if any)
  cpg.genotype_v11_id             AS clutch_primary_genotype_v11_id,
  cpg.clutch_genotype_basecodes   AS clutch_primary_genotype_basecodes,
  cpg.clutch_genotype_pretty      AS clutch_primary_genotype_pretty,
  -- expected (possible) genotypes from parent alleles
  cg.genotype_v11_id              AS expected_genotype_v11_id,
  g.genotype_code                 AS expected_genotype_code,
  g.genotype_basecodes            AS expected_genotype_basecodes,
  g.genotype_pretty               AS expected_genotype_pretty,
  cg.expected_fraction,
  cg.expected_label,
  cg.notes,
  cg.created_by,
  -- treatments (from v11_clutch_star)
  cs.treat_codes,
  cs.treat_basecodes,
  cs.expected_genotype_basecodes  AS legacy_expected_genotype_basecodes
FROM public.clutches c
LEFT JOIN public.v11_clutch_parent_genotypes cpg
  ON cpg.clutch_id = c.id
LEFT JOIN public.clutch_genotypes_v11 cg
  ON cg.clutch_id = c.id
LEFT JOIN public.genotypes_v11 g
  ON g.id = cg.genotype_v11_id
LEFT JOIN public.v11_clutch_star cs
  ON cs.clutch_id = c.id
WHERE cg.created_by = 'v11_seed_clutch_expected_genotypes_from_parents';

COMMENT ON VIEW public.v11_clutch_expected_genotype_star IS
  'v11 clutch expected genotype star: per clutch, parent fish + primary genotype + parent-based possible genotypes from clutch_genotypes_v11, including treatment codes.';

COMMIT;
