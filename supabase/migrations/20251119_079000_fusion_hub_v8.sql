BEGIN;

----------------------------------------------------------------------
-- v8: Fluorophore hub centered on fusions
--
-- 1. genotype_fusions: which fusions are implied by a genotype
-- 2. treatment_fusions: which fusions are delivered by a treatment
-- 3. v_fusion_sources: unified view of "where is this fusion used?"
--
-- Assumes:
--   - genotypes(genotype_code) exists
--   - fusions(id, fluor_id, tag_id, ...) exists
--   - fluors(id, fluor_code, ...) exists
--   - tags(id, tag_code, ...) exists
----------------------------------------------------------------------

-- 1. genotype_fusions table
CREATE TABLE IF NOT EXISTS public.genotype_fusions (
  genotype_code  text NOT NULL
    REFERENCES public.genotypes(genotype_code)
    ON UPDATE CASCADE ON DELETE CASCADE,
  fusion_id      uuid NOT NULL
    REFERENCES public.fusions(id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  source         text NOT NULL,   -- e.g. 'derived_from_alleles', 'manual'
  source_detail  text,
  PRIMARY KEY (genotype_code, fusion_id, source)
);

-- 2. treatment_fusions table
--    NOTE: treatment_id can be adapted once your treatment model is solidified.
CREATE TABLE IF NOT EXISTS public.treatment_fusions (
  treatment_id   uuid NOT NULL,
  fusion_id      uuid NOT NULL
    REFERENCES public.fusions(id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  source         text NOT NULL,   -- 'plasmid', 'rna', 'dye', 'protein', 'manual', ...
  source_detail  text,
  PRIMARY KEY (treatment_id, fusion_id, source)
);

-- 3. Unified fusion hub view: v_fusion_sources
DROP VIEW IF EXISTS public.v_fusion_sources CASCADE;

CREATE VIEW public.v_fusion_sources AS
  -- Genotype contexts
  SELECT
    'genotype'                 AS source_type,
    gf.genotype_code           AS genotype_code,
    NULL::uuid                 AS treatment_id,
    fu.id                      AS fusion_id,
    fl.id                      AS fluor_id,
    fl.fluor_code,
    tg.id                      AS tag_id,
    tg.tag_code,
    gf.source,
    gf.source_detail
  FROM public.genotype_fusions gf
  JOIN public.fusions fu  ON fu.id = gf.fusion_id
  JOIN public.fluors fl   ON fl.id = fu.fluor_id
  LEFT JOIN public.tags tg ON tg.id = fu.tag_id

  UNION ALL

  -- Treatment contexts
  SELECT
    'treatment'                AS source_type,
    NULL::text                 AS genotype_code,
    tf.treatment_id,
    fu.id                      AS fusion_id,
    fl.id                      AS fluor_id,
    fl.fluor_code,
    tg.id                      AS tag_id,
    tg.tag_code,
    tf.source,
    tf.source_detail
  FROM public.treatment_fusions tf
  JOIN public.fusions fu  ON fu.id = tf.fusion_id
  JOIN public.fluors fl   ON fl.id = fu.fluor_id
  LEFT JOIN public.tags tg ON tg.id = fu.tag_id;

COMMIT;
