BEGIN;

-- 1) Drop views if they exist
DROP VIEW IF EXISTS public.v11_fish_line_star;
DROP VIEW IF EXISTS public.v11_fish_group_star;
DROP VIEW IF EXISTS public.v11_fish_instance_duplicates;

-- 2) v11_fish_line_star
CREATE VIEW public.v11_fish_line_star AS
WITH line_core AS (
  SELECT
    fl.id                AS line_id,
    fl.line_code,
    fl.nickname          AS line_nickname,
    fl.genetic_background,
    fl.line_building_stage,
    fl.construct_code    AS line_construct_code
  FROM public.fish_lines fl
),
instances AS (
  SELECT
    fi.id       AS fish_instance_id,
    fi.line_id,
    fi.instance_stage,
    fi.birthday
  FROM public.fish_instances_v10 fi
),
alleles AS (
  SELECT
    fi.line_id,
    fta.transgene_base_code,
    ta.allele_number,
    ta.allele_name,
    ta.allele_nickname
  FROM public.fish_instances_v10 fi
  JOIN public.fish_transgene_alleles fta
    ON fta.fish_id = fi.id
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
),
allele_rollups AS (
  SELECT
    line_id,
    string_agg(
      DISTINCT format('%s:%s', transgene_base_code, COALESCE(allele_nickname, allele_name)),
      '||' ORDER BY format('%s:%s', transgene_base_code, COALESCE(allele_nickname, allele_name))
    ) AS line_allele_nick_rollup,
    string_agg(
      DISTINCT format('%s:%s', transgene_base_code, allele_name),
      '||' ORDER BY format('%s:%s', transgene_base_code, allele_name)
    ) AS line_allele_name_rollup,
    string_agg(
      DISTINCT transgene_base_code,
      '||' ORDER BY transgene_base_code
    ) AS line_transgene_rollup
  FROM alleles
  GROUP BY line_id
),
genotypes AS (
  SELECT
    fi.line_id,
    cr.genotype_basecodes
  FROM public.fish_instances_v10 fi
  JOIN public.v11_fish_construct_rollups cr
    ON cr.fish_instance_id = fi.id
),
genotype_rollups AS (
  SELECT
    line_id,
    string_agg(
      DISTINCT genotype_basecodes,
      '||' ORDER BY genotype_basecodes
    ) AS line_genotype_basecodes
  FROM genotypes
  GROUP BY line_id
)
SELECT
  lc.line_id,
  lc.line_code,
  lc.line_nickname,
  lc.genetic_background,
  lc.line_building_stage,
  lc.line_construct_code,
  ar.line_allele_nick_rollup,
  ar.line_allele_name_rollup,
  ar.line_transgene_rollup,
  gr.line_genotype_basecodes
FROM line_core lc
LEFT JOIN allele_rollups ar
  ON ar.line_id = lc.line_id
LEFT JOIN genotype_rollups gr
  ON gr.line_id = lc.line_id;

COMMENT ON VIEW public.v11_fish_line_star IS
  'v11: per-line rollup of alleles (nick + guN) and construct-based genotypes across all fish instances of that line.';

-- 3) v11_fish_group_star
CREATE VIEW public.v11_fish_group_star AS
WITH line_star AS (
  SELECT
    line_id,
    line_code,
    line_nickname,
    genetic_background,
    line_building_stage,
    line_transgene_rollup
  FROM public.v11_fish_line_star
),
grouped AS (
  SELECT
    line_transgene_rollup,
    string_agg(DISTINCT line_code, '||' ORDER BY line_code)           AS group_line_codes,
    string_agg(DISTINCT line_nickname, '||' ORDER BY line_nickname)   AS group_line_nicknames,
    string_agg(DISTINCT genetic_background, '||' ORDER BY genetic_background) AS group_genetic_backgrounds
  FROM line_star
  WHERE line_transgene_rollup IS NOT NULL
    AND line_transgene_rollup <> ''
  GROUP BY line_transgene_rollup
)
SELECT
  line_transgene_rollup AS group_transgene_rollup,
  group_line_codes,
  group_line_nicknames,
  group_genetic_backgrounds
FROM grouped;

COMMENT ON VIEW public.v11_fish_group_star IS
  'v11: groups of lines sharing the same transgene base_code set (ignoring allele_number).';

-- 4) v11_fish_instance_duplicates (diagnostic)
CREATE VIEW public.v11_fish_instance_duplicates AS
SELECT
  fi.genotype_v11_id,
  fi.instance_stage,
  fi.birthday,
  COUNT(*) AS n_instances,
  string_agg(fish_code, '||' ORDER BY fish_code) AS fish_codes
FROM public.fish_instances_v10 fi
WHERE fi.genotype_v11_id IS NOT NULL
  AND fi.instance_stage IS NOT NULL
  AND fi.birthday IS NOT NULL
GROUP BY fi.genotype_v11_id, fi.instance_stage, fi.birthday
HAVING COUNT(*) > 1;

COMMENT ON VIEW public.v11_fish_instance_duplicates IS
  'Diagnostic: fish_instances that share (genotype_v11_id, instance_stage, birthday), potential duplicates.';

COMMIT;
