BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_instance_star AS
WITH fish_core AS (
  SELECT
    fi.id            AS fish_instance_id,
    fi.fish_code,
    fi.line_id,
    fi.birthday,
    fi.instance_stage,
    fi.genotype_v11_id AS fish_genotype_v11_id
  FROM public.fish_instances_v10 fi
),
line_info AS (
  SELECT
    fl.id                AS line_id,
    fl.line_code,
    fl.nickname          AS line_nickname,
    fl.genetic_background,
    fl.construct_code    AS line_construct_code
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
  SELECT DISTINCT ON (g.genotype_basecodes)
    g.id,
    g.genotype_code,
    g.genotype_basecodes,
    g.genotype_pretty
  FROM public.genotypes_v11 g
  ORDER BY
    g.genotype_basecodes,
    g.created_at DESC,
    g.id DESC
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
LEFT JOIN line_info  li ON li.line_id            = fc.line_id
LEFT JOIN alleles    al ON al.fish_instance_id   = fc.fish_instance_id
LEFT JOIN constructs c  ON c.fish_instance_id    = fc.fish_instance_id
LEFT JOIN genos      g  ON g.genotype_basecodes  = c.genotype_basecodes;

COMMENT ON VIEW public.v11_fish_instance_star IS
  'v11 fish instance star: line + background + allele rollups + construct-based genotype + canonical v11 genotype (preferring latest, typically allele-based).';

COMMIT;
