BEGIN;

----------------------------------------------------------------------
-- v8: Dyes as real fluorophores (Option A)
--
-- Goal:
--   Every dye in the system corresponds to a row in public.fluors,
--   and references it via dyes.fluor_id.
--
-- After this:
--   - dyes.fluor_id → fluors.id
--   - treatment_fluors can include entries with source='dye'
--     by resolving dyes.fluor_id and inserting fluor_id there.
----------------------------------------------------------------------

-- 1. Add fluor_id column to dyes if it does not exist
ALTER TABLE public.dyes
  ADD COLUMN IF NOT EXISTS fluor_id uuid;

-- 2. Add foreign key from dyes.fluor_id to fluors.id
ALTER TABLE public.dyes
  DROP CONSTRAINT IF EXISTS dyes_fluor_id_fkey;

ALTER TABLE public.dyes
  ADD CONSTRAINT dyes_fluor_id_fkey
  FOREIGN KEY (fluor_id)
  REFERENCES public.fluors(id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

-- 3. Optional: enforce at most one dye per fluor (1:1 mapping)
--    Comment this out if you ever expect multiple dye records per fluor.
ALTER TABLE public.dyes
  DROP CONSTRAINT IF EXISTS dyes_fluor_id_key;

ALTER TABLE public.dyes
  ADD CONSTRAINT dyes_fluor_id_key UNIQUE (fluor_id);

COMMIT;
