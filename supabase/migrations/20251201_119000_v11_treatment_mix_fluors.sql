BEGIN;

DROP VIEW IF EXISTS public.v11_treatment_mix_fluors;

CREATE VIEW public.v11_treatment_mix_fluors AS
SELECT
  mix_id,
  treatment_id,
  treat_code,
  kind_code,
  mix_code,
  fluor_codes,
  fluor_names,
  tag_codes,
  -- label for fluors at the mix level (used by v11_clutch_star_final)
  COALESCE(NULLIF(fluor_names, ''), fluor_codes) AS fluor_tag,
  -- placeholder organelle rollup at the mix level (v11_clutch_star_final expects this column)
  ''::text AS organelle_fluor
FROM public.v10_treatment_mix_fluors;

COMMIT;
