BEGIN;

-- Drop old duplicate views if they exist
DROP VIEW IF EXISTS public.v11_fish_instance_duplicates_detail;
DROP VIEW IF EXISTS public.v11_fish_instance_duplicates;
DROP VIEW IF EXISTS public.v11_fish_instance_allele_keys;

-- 1) Helper view: per-fish allele_nick_rollup
CREATE VIEW public.v11_fish_instance_allele_keys AS
SELECT
  fi.id AS fish_instance_id,
  string_agg(
    DISTINCT format(
      '%s:%s',
      fta.transgene_base_code,
      COALESCE(ta.allele_nickname, ta.allele_name)
    ),
    '||' ORDER BY format(
      '%s:%s',
      fta.transgene_base_code,
      COALESCE(ta.allele_nickname, ta.allele_name)
    )
  ) AS allele_nick_rollup
FROM public.fish_instances_v10 fi
LEFT JOIN public.fish_transgene_alleles fta
  ON fta.fish_id = fi.id
LEFT JOIN public.transgene_alleles ta
  ON ta.transgene_base_code = fta.transgene_base_code
 AND ta.allele_number       = fta.allele_number
GROUP BY fi.id;

COMMENT ON VIEW public.v11_fish_instance_allele_keys IS
  'Per-fish allele_nick_rollup: sorted distinct transgene_base_code:allele_nickname_or_name for each fish_instance.';

-- 2) Summary duplicates: same allele_nick_rollup + stage + birthday
CREATE VIEW public.v11_fish_instance_duplicates AS
SELECT
  fi.genotype_v11_id,
  fi.instance_stage,
  fi.birthday,
  ak.allele_nick_rollup,
  COUNT(*) AS n_instances,
  string_agg(fi.fish_code, '||' ORDER BY fi.fish_code) AS fish_codes
FROM public.fish_instances_v10 fi
JOIN public.v11_fish_instance_allele_keys ak
  ON ak.fish_instance_id = fi.id
WHERE fi.instance_stage IS NOT NULL
  AND fi.birthday IS NOT NULL
  AND ak.allele_nick_rollup IS NOT NULL
  AND ak.allele_nick_rollup <> ''
GROUP BY fi.genotype_v11_id, fi.instance_stage, fi.birthday, ak.allele_nick_rollup
HAVING COUNT(*) > 1;

COMMENT ON VIEW public.v11_fish_instance_duplicates IS
  'Allele-aware diagnostic: fish_instances sharing (allele_nick_rollup, instance_stage, birthday), potential conceptual duplicates.';

-- 3) Detail view: list each fish_instance in those duplicate groups
CREATE VIEW public.v11_fish_instance_duplicates_detail AS
SELECT
  dk.genotype_v11_id,
  dk.instance_stage,
  dk.birthday,
  dk.allele_nick_rollup,
  dk.n_instances,
  fi.id::text        AS fish_instance_id,
  fi.fish_code,
  fi.line_id::text   AS line_id,
  fl.line_code,
  fl.nickname        AS line_nickname,
  fl.genetic_background
FROM public.v11_fish_instance_duplicates dk
JOIN public.fish_instances_v10 fi
  ON fi.genotype_v11_id = dk.genotype_v11_id
 AND fi.instance_stage   = dk.instance_stage
 AND fi.birthday         = dk.birthday
JOIN public.v11_fish_instance_allele_keys ak
  ON ak.fish_instance_id = fi.id
 AND ak.allele_nick_rollup = dk.allele_nick_rollup
LEFT JOIN public.fish_lines fl
  ON fl.id = fi.line_id
ORDER BY dk.n_instances DESC,
         dk.genotype_v11_id,
         dk.instance_stage,
         dk.birthday,
         dk.allele_nick_rollup,
         fi.fish_code;

COMMENT ON VIEW public.v11_fish_instance_duplicates_detail IS
  'Allele-aware detail: all fish_instances sharing (allele_nick_rollup, instance_stage, birthday), for manual inspection.';

COMMIT;
