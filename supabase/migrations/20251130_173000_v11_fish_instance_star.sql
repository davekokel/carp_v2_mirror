BEGIN;

DROP VIEW IF EXISTS public.v11_fish_instance_star;

CREATE VIEW public.v11_fish_instance_star AS
SELECT
  fi.id                  AS fish_instance_id,
  fi.fish_code           AS fish_code,
  g.genotype_pretty      AS genotype_pretty,
  g.genotype_basecodes   AS genotype_basecodes
FROM public.fish_instances_v10 fi
LEFT JOIN public.genotypes_v11 g
  ON g.id = fi.genotype_v11_id;

COMMENT ON VIEW public.v11_fish_instance_star IS
  'v11 fish instance star: minimal view used to seed fish_genotypes_v11; exposes fish_instance_id, fish_code, genotype_pretty, genotype_basecodes.';

COMMIT;
