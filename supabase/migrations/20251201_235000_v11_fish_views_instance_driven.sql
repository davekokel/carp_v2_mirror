BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_instance_star AS
WITH fish_core AS (
         SELECT
           fi.id                    AS fish_instance_id,
           fi.fish_code,
           fi.line_id,
           fi.birthday,
           fi.instance_stage,
           fi.genetic_background    AS genetic_background,
           fi.genotype_v11_id       AS fish_genotype_v11_id
         FROM public.fish_instances_v10 fi
     ), line_info AS (
         SELECT
           fl.id                    AS line_id,
           fl.line_code,
           fl.nickname              AS line_nickname,
           fl.genetic_background,
           fl.construct_code        AS line_construct_code
         FROM public.fish_lines fl
     ), alleles AS (
         SELECT
           fa.fish_instance_id,
           fa.allele_canonical_rollup,
           fa.allele_label_rollup
         FROM public.v11_fish_allele_rollups fa
     ), constructs AS (
         SELECT
           cr.fish_instance_id,
           cr.genotype_basecodes
         FROM public.v11_fish_construct_rollups cr
     ), genos_rollup AS (
         SELECT DISTINCT ON (g1.genotype_basecodes)
           g1.id,
           g1.genotype_code,
           g1.genotype_basecodes,
           g1.genotype_pretty
         FROM public.genotypes_v11 g1
         ORDER BY g1.genotype_basecodes, g1.created_at DESC, g1.id DESC
     )
SELECT
  fc.fish_instance_id,
  fc.fish_code,
  fc.birthday,
  fc.instance_stage,
  li.line_code,
  li.line_nickname,
  fc.genetic_background       AS genetic_background,
  li.line_construct_code,
  al.allele_canonical_rollup,
  al.allele_label_rollup,
  COALESCE(g_direct.genotype_basecodes, c.genotype_basecodes) AS genotype_basecodes,
  COALESCE(fc.fish_genotype_v11_id, g_rollup.id)               AS genotype_v11_id,
  COALESCE(g_direct.genotype_code, g_rollup.genotype_code)     AS genotype_code,
  COALESCE(g_direct.genotype_pretty, g_rollup.genotype_pretty) AS genotype_pretty
FROM fish_core fc
LEFT JOIN line_info li
  ON li.line_id = fc.line_id
LEFT JOIN alleles al
  ON al.fish_instance_id = fc.fish_instance_id
LEFT JOIN constructs c
  ON c.fish_instance_id = fc.fish_instance_id
LEFT JOIN genos_rollup g_rollup
  ON g_rollup.genotype_basecodes = c.genotype_basecodes
LEFT JOIN public.genotypes_v11 g_direct
  ON g_direct.id = fc.fish_genotype_v11_id;

CREATE OR REPLACE VIEW public.v11_fish_line_star AS
WITH base AS (
  SELECT
    fl.id                    AS line_id,
    fl.line_code,
    fl.nickname              AS line_nickname,
    fis.genetic_background   AS genetic_background,
    fis.instance_stage       AS instance_stage,
    fl.construct_code        AS line_construct_code,
    fi.id                    AS fish_instance_id,
    fi.birthday,
    fis.genotype_pretty      AS genotype_pretty
  FROM public.fish_lines fl
  LEFT JOIN public.fish_instances_v10 fi
    ON fi.line_id = fl.id
  LEFT JOIN public.v11_fish_instance_star fis
    ON fis.fish_instance_id = fi.id
)
SELECT
  line_id,
  line_code,
  max(line_nickname)          AS line_nickname,
  max(genetic_background)     AS genetic_background,
  max(instance_stage)         AS line_building_stage,
  max(line_construct_code)    AS line_construct_code,
  max(line_construct_code)    AS line_transgene_rollup,
  min(birthday)               AS first_birthday,
  max(birthday)               AS last_birthday,
  count(fish_instance_id)     AS n_instances,
  max(genotype_pretty)        AS genotype_pretty
FROM base
GROUP BY line_id, line_code
ORDER BY line_code;

COMMIT;
