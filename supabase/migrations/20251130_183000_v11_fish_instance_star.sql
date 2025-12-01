BEGIN;

DROP VIEW IF EXISTS public.v11_fish_instance_star;

CREATE VIEW public.v11_fish_instance_star AS
WITH fish_core AS (
  SELECT
    fi.id               AS fish_instance_id,
    fi.fish_code,
    fi.line_id,
    fi.birthday,
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
  li.line_code,
  li.line_nickname,
  li.genetic_background,
  li.line_construct_code,
  al.allele_canonical_rollup,
  al.allele_label_rollup,
  c.genotype_basecodes,
  -- prefer explicit fish_genotype_v11_id if set; else from genotypes_v11 via basecodes
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
  'v11 fish instance star: fish + line + allele + canonical construct genotype rollups.';

COMMIT;
