BEGIN;

CREATE OR REPLACE VIEW public.v_roi_overview_markers AS
SELECT
  v.*,
  -- TRUE fusions only: genotype-side fusion labels
  v.genotype_fusions_rollup AS fluors_rollup,
  -- Full fluor marker rollup: genotype + treatments + dyes (legacy)
  v.fluors_rollup           AS markers_rollup
FROM public.v_roi_overview v;

COMMIT;
