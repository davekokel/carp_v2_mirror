BEGIN;

----------------------------------------------------------------------
-- v8: Make fish_instance.standard_genotype_code canonical
--     and turn join_fish_genotypes into a compatibility VIEW.
--
-- Assumes:
--   - fish_instance has column standard_genotype_code (text FK → genotypes.genotype_code)
--   - join_fish_genotypes table currently has (fish_id, genotype_id) FK → genotypes(id)
----------------------------------------------------------------------

-- 1. Best-effort copy from join_fish_genotypes into fish_instance.standard_genotype_code.
--    We resolve genotype_id → genotype_code via genotypes.
DO $$
BEGIN
  IF to_regclass('public.join_fish_genotypes') IS NOT NULL THEN
    UPDATE public.fish_instance f
    SET standard_genotype_code = j.genotype_code
    FROM (
      SELECT DISTINCT
        j.fish_id,
        g.genotype_code
      FROM public.join_fish_genotypes j
      JOIN public.genotypes g
        ON g.id = j.genotype_id
    ) AS j
    WHERE f.id = j.fish_id
      AND f.standard_genotype_code IS NULL;
  END IF;
END $$;

-- 2. Drop the legacy join table if it still exists
DROP TABLE IF EXISTS public.join_fish_genotypes CASCADE;

-- 3. Recreate join_fish_genotypes as a VIEW for compatibility
DROP VIEW IF EXISTS public.join_fish_genotypes CASCADE;

CREATE VIEW public.join_fish_genotypes AS
SELECT
  f.id                   AS fish_id,
  f.standard_genotype_code AS genotype_code
FROM public.fish_instance f
WHERE f.standard_genotype_code IS NOT NULL;

COMMIT;
