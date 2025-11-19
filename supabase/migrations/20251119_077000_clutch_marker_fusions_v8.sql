BEGIN;

----------------------------------------------------------------------
-- v8: Make fusions the canonical hub for clutch-level fluor markers.
--
-- Old shape:
--   clutch_fluor_markers (clutch_id → fluors.id)
-- New shape:
--   clutch_marker_fusions (clutch_id → fusions.id)
--   v_clutch_fluors_overview is a view: clutches → fusions → fluors
----------------------------------------------------------------------

-- 1. Drop the old overview view if it exists
DROP VIEW IF EXISTS public.v_clutch_fluors_overview CASCADE;

-- 2. Drop the old clutch_fluor_markers table if it exists
DROP TABLE IF EXISTS public.clutch_fluor_markers CASCADE;

-- 3. Create the canonical join table: clutch ↔ fusion
CREATE TABLE public.clutch_marker_fusions (
  clutch_id    uuid NOT NULL REFERENCES public.clutches(id)
                         ON UPDATE CASCADE ON DELETE CASCADE,
  fusion_id    uuid NOT NULL REFERENCES public.fusions(id)
                         ON UPDATE CASCADE ON DELETE RESTRICT,
  source       text NOT NULL,   -- 'genotype', 'treatment', 'unknown', ...
  source_detail text,           -- e.g. genotype_code, plasmid_code, RNA code, ROI example
  PRIMARY KEY (clutch_id, fusion_id, source)
);

-- 4. Recreate the clutch↔fluor view via fusions
CREATE VIEW public.v_clutch_fluors_overview AS
SELECT
  cl.id              AS clutch_id,
  cl.clutch_code,
  cl.clutch_date,
  cmf.fusion_id,
  f.id               AS fluor_id,
  f.fluor_code,
  f.fluor_name,
  f.excitation_nm,
  f.emission_nm,
  cmf.source,
  cmf.source_detail
FROM public.clutches cl
JOIN public.clutch_marker_fusions cmf
  ON cmf.clutch_id = cl.id
JOIN public.fusions fu
  ON fu.id = cmf.fusion_id
JOIN public.fluors f
  ON f.id = fu.fluor_id;

COMMIT;
