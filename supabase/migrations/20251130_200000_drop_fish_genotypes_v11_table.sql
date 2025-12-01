BEGIN;

-- If any old code still refers to fish_genotypes_v11 as a table,
-- we'll replace it with a view that reflects the canonical one-genotype-per-fish link.

-- Drop the table if it exists
DROP TABLE IF EXISTS public.fish_genotypes_v11;

-- Recreate as a compatibility view over fish_instances_v10
CREATE VIEW public.fish_genotypes_v11 AS
SELECT
  fi.id          AS fish_id,
  fi.genotype_v11_id AS genotype_id,
  fi.created_at  AS created_at
FROM public.fish_instances_v10 fi
WHERE fi.genotype_v11_id IS NOT NULL;

COMMENT ON VIEW public.fish_genotypes_v11 IS
  'Compatibility view: each fish_instance has at most one genotype_v11_id; this view reflects that one-to-one relation.';

COMMIT;
