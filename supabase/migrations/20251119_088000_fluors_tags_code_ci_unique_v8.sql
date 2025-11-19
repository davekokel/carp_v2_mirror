BEGIN;

----------------------------------------------------------------------
-- v8: Global standard for code fields: case-insensitive uniqueness
--
-- Enforce that there cannot be multiple fluors or tags whose codes
-- differ only by case.
--
-- We do NOT change stored values; we just add case-insensitive
-- unique indexes to guarantee invariants going forward.
----------------------------------------------------------------------

-- Fluors: enforce UNIQUE lower(fluor_code)
DROP INDEX IF EXISTS public.uniq_fluors_code_ci;

CREATE UNIQUE INDEX uniq_fluors_code_ci
  ON public.fluors (lower(fluor_code));

-- Tags: enforce UNIQUE lower(tag_code)
DROP INDEX IF EXISTS public.uniq_tags_code_ci;

CREATE UNIQUE INDEX uniq_tags_code_ci
  ON public.tags (lower(tag_code));

COMMIT;
