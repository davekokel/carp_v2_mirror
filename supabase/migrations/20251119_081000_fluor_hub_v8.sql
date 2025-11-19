BEGIN;

----------------------------------------------------------------------
-- v8: Fluorophore hub
--
-- Core idea:
--   - fluors = photophysical hub
--   - genotype_fluors = fluors implied by genotypes (from genotype_fusions)
--   - treatment_fluors = fluors implied by treatments (from treatment_fusions and dyes)
--   - v_fluor_sources = unified view over both
--
-- Assumes:
--   - public.fluors(id, fluor_code, fluor_name, excitation_nm, emission_nm, ...)
--   - public.fusions(id, fluor_id, tag_id, ...) exists
--   - public.tags(id, tag_code, ...) exists
--   - public.genotypes(genotype_code) exists
--   - public.treatments(id, treatment_code, ...) exists
--   - public.genotype_fusions(genotype_code, fusion_id, source, source_detail) exists
--   - public.treatment_fusions(treatment_id, fusion_id, source, source_detail) exists
----------------------------------------------------------------------

----------------------------------------------------------------------
-- 1. genotype_fluors: fluor content implied by a genotype
----------------------------------------------------------------------

-- If an old genotype_fluor_markers table exists, adopt it as genotype_fluors.
DO $$
BEGIN
  IF to_regclass('public.genotype_fluor_markers') IS NOT NULL
     AND to_regclass('public.genotype_fluors') IS NULL THEN
    ALTER TABLE public.genotype_fluor_markers
      RENAME TO genotype_fluors;
  END IF;
END $$;

-- Create genotype_fluors if it doesn't exist yet
CREATE TABLE IF NOT EXISTS public.genotype_fluors (
  genotype_code text NOT NULL
    REFERENCES public.genotypes(genotype_code)
    ON UPDATE CASCADE ON DELETE CASCADE,
  fluor_id      uuid NOT NULL
    REFERENCES public.fluors(id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  source        text NOT NULL,   -- 'derived_from_fusions', 'manual', etc.
  source_detail text,
  PRIMARY KEY (genotype_code, fluor_id, source)
);

----------------------------------------------------------------------
-- 2. treatment_fluors: fluor content implied by a treatment
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.treatment_fluors (
  treatment_id  uuid NOT NULL
    REFERENCES public.treatments(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  fluor_id      uuid NOT NULL
    REFERENCES public.fluors(id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  source        text NOT NULL,   -- 'fusion', 'dye', 'manual', ...
  source_detail text,
  PRIMARY KEY (treatment_id, fluor_id, source)
);

----------------------------------------------------------------------
-- 3. v_fluor_sources: unified fluorophore hub view
--    (genotype_fluors ∪ treatment_fluors with attached metadata)
----------------------------------------------------------------------

DROP VIEW IF EXISTS public.v_fluor_sources CASCADE;

CREATE VIEW public.v_fluor_sources AS
  -- Genotype-level fluor markers
  SELECT
    'genotype'              AS source_type,
    gf.genotype_code        AS genotype_code,
    NULL::uuid              AS treatment_id,
    fl.id                   AS fluor_id,
    fl.fluor_code,
    fl.fluor_name,
    fl.excitation_nm,
    fl.emission_nm,
    gf.source,
    gf.source_detail
  FROM public.genotype_fluors gf
  JOIN public.fluors fl
    ON fl.id = gf.fluor_id

  UNION ALL

  -- Treatment-level fluor markers (fusions + dyes)
  SELECT
    'treatment'             AS source_type,
    NULL::text              AS genotype_code,
    tf.treatment_id,
    fl.id                   AS fluor_id,
    fl.fluor_code,
    fl.fluor_name,
    fl.excitation_nm,
    fl.emission_nm,
    tf.source,
    tf.source_detail
  FROM public.treatment_fluors tf
  JOIN public.fluors fl
    ON fl.id = tf.fluor_id;

COMMIT;
