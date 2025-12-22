BEGIN;

DO $$
DECLARE n_dup int;
DECLARE n_blank int;
BEGIN
  SELECT count(*) INTO n_dup
  FROM (
    SELECT genotype_basecodes
    FROM public.genotypes_v11
    WHERE coalesce(btrim(genotype_basecodes),'') <> ''
    GROUP BY genotype_basecodes
    HAVING count(*) > 1
  ) d;

  IF n_dup <> 0 THEN
    RAISE EXCEPTION '[STOP] genotypes_v11 has duplicated genotype_basecodes keys: %', n_dup;
  END IF;

  SELECT count(*) INTO n_blank
  FROM public.genotypes_v11
  WHERE coalesce(btrim(genotype_basecodes),'') = '';

  IF n_blank <> 0 THEN
    RAISE EXCEPTION '[STOP] genotypes_v11 has blank genotype_basecodes rows: %', n_blank;
  END IF;
END $$;

ALTER TABLE public.genotypes_v11
  ALTER COLUMN genotype_basecodes SET NOT NULL;

ALTER TABLE public.genotypes_v11
  ADD CONSTRAINT genotypes_v11_genotype_basecodes_key UNIQUE (genotype_basecodes);

CREATE OR REPLACE VIEW public.v11_fish_instance_star AS
WITH fish_core AS (
  SELECT
    fi.id AS fish_instance_id,
    fi.fish_code,
    fi.line_id,
    fi.birthday,
    fi.instance_stage,
    fi.genetic_background,
    fi.genotype_v11_id AS fish_genotype_v11_id
  FROM public.fish_instances_v10 fi
),
line_info AS (
  SELECT
    fl.id AS line_id,
    fl.line_code,
    fl.nickname AS line_nickname,
    fl.genetic_background,
    fl.construct_code AS line_construct_code
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
)
SELECT
  fc.fish_instance_id,
  fc.fish_code,
  fc.birthday,
  fc.instance_stage,
  li.line_code,
  li.line_nickname,
  fc.genetic_background,
  li.line_construct_code,
  al.allele_canonical_rollup,
  al.allele_label_rollup,
  COALESCE(g_direct.genotype_basecodes, c.genotype_basecodes) AS genotype_basecodes,
  COALESCE(fc.fish_genotype_v11_id, g_rollup.id) AS genotype_v11_id,
  COALESCE(g_direct.genotype_code, g_rollup.genotype_code) AS genotype_code,
  COALESCE(g_direct.genotype_pretty, g_rollup.genotype_pretty) AS genotype_pretty
FROM fish_core fc
LEFT JOIN line_info li
  ON li.line_id = fc.line_id
LEFT JOIN alleles al
  ON al.fish_instance_id = fc.fish_instance_id
LEFT JOIN constructs c
  ON c.fish_instance_id = fc.fish_instance_id
LEFT JOIN public.genotypes_v11 g_rollup
  ON g_rollup.genotype_basecodes = c.genotype_basecodes
LEFT JOIN public.genotypes_v11 g_direct
  ON g_direct.id = fc.fish_genotype_v11_id;

COMMIT;
