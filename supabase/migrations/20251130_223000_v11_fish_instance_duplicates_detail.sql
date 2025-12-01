BEGIN;

DROP VIEW IF EXISTS public.v11_fish_instance_duplicates_detail;

CREATE VIEW public.v11_fish_instance_duplicates_detail AS
WITH dup_keys AS (
  SELECT
    fi.genotype_v11_id,
    fi.instance_stage,
    fi.birthday,
    COUNT(*) AS n_instances
  FROM public.fish_instances_v10 fi
  WHERE fi.genotype_v11_id IS NOT NULL
    AND fi.instance_stage IS NOT NULL
    AND fi.birthday IS NOT NULL
  GROUP BY fi.genotype_v11_id, fi.instance_stage, fi.birthday
  HAVING COUNT(*) > 1
)
SELECT
  dk.genotype_v11_id,
  dk.instance_stage,
  dk.birthday,
  dk.n_instances,
  fi.id::text        AS fish_instance_id,
  fi.fish_code,
  fi.line_id::text   AS line_id,
  fl.line_code,
  fl.nickname        AS line_nickname,
  fl.genetic_background
FROM dup_keys dk
JOIN public.fish_instances_v10 fi
  ON fi.genotype_v11_id = dk.genotype_v11_id
 AND fi.instance_stage   = dk.instance_stage
 AND fi.birthday         = dk.birthday
LEFT JOIN public.fish_lines fl
  ON fl.id = fi.line_id
ORDER BY dk.n_instances DESC,
         dk.genotype_v11_id,
         dk.instance_stage,
         dk.birthday,
         fi.fish_code;

COMMENT ON VIEW public.v11_fish_instance_duplicates_detail IS
  'Detail: all fish_instances that share (genotype_v11_id, instance_stage, birthday), one row per fish instance, for manual duplicate inspection.';

COMMIT;
