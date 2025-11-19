BEGIN;

----------------------------------------------------------------------
-- v8: Fluorophore hub + unified fluor marker view
--
-- 1. genotype_fluor_markers: which fluor(s) are implied by a genotype
-- 2. v_all_fluor_markers: combine genotype-level and clutch-level
--    fluor markers into one unified view centered on fluors.
--
-- Assumptions:
--   - genotypes(genotype_code) exists
--   - fluors(id, fluor_code, fluor_name, excitation_nm, emission_nm) exists
--   - v_clutch_fluors_overview exists and exposes:
--       clutch_id, clutch_code, clutch_date,
--       fluor_id, fluor_code, fluor_name, excitation_nm, emission_nm,
--       source, source_detail
----------------------------------------------------------------------

-- 1. Drop old unified view if present
DROP VIEW IF EXISTS public.v_all_fluor_markers CASCADE;

-- 2. Create canonical genotype→fluor join table
CREATE TABLE IF NOT EXISTS public.genotype_fluor_markers (
  genotype_code text NOT NULL
    REFERENCES public.genotypes(genotype_code)
    ON UPDATE CASCADE ON DELETE CASCADE,
  fluor_id      uuid NOT NULL
    REFERENCES public.fluors(id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  source        text NOT NULL,   -- e.g. 'derived_from_alleles', 'manual_override'
  source_detail text,            -- e.g. which alleles/fusions were used to infer this
  PRIMARY KEY (genotype_code, fluor_id, source)
);

-- 3. Unified fluor marker view: genotype-level + clutch-level
CREATE VIEW public.v_all_fluor_markers AS
  -- Genotype-level markers
  SELECT
    'genotype'           AS marker_level,
    gfm.genotype_code    AS genotype_code,
    NULL::uuid           AS clutch_id,
    NULL::text           AS clutch_code,
    NULL::date           AS clutch_date,
    gfm.fluor_id,
    f.fluor_code,
    f.fluor_name,
    f.excitation_nm,
    f.emission_nm,
    gfm.source,
    gfm.source_detail
  FROM public.genotype_fluor_markers gfm
  JOIN public.fluors f
    ON f.id = gfm.fluor_id

  UNION ALL

  -- Clutch-level markers (genotype + treatments folded together),
  -- derived via v_clutch_fluors_overview.
  SELECT
    'clutch'             AS marker_level,
    NULL::text           AS genotype_code,
    cfo.clutch_id,
    cfo.clutch_code,
    cfo.clutch_date,
    cfo.fluor_id,
    cfo.fluor_code,
    cfo.fluor_name,
    cfo.excitation_nm,
    cfo.emission_nm,
    cfo.source,
    cfo.source_detail
  FROM public.v_clutch_fluors_overview cfo;

COMMIT;
