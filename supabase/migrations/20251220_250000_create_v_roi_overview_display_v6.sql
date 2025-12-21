BEGIN;

DROP VIEW IF EXISTS public.v_roi_overview_display_v6;

CREATE VIEW public.v_roi_overview_display_v6 AS
SELECT
  r.*,

  CASE
    WHEN coalesce(btrim(r.treatment_text),'') <> '' THEN
      r.treatment_text || ' > ' ||
      coalesce(nullif(btrim(r.marker_rollup_display_tg),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(r.marker_rollup_display_tg),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
  END AS tx_gt_tg,

  CASE
    WHEN coalesce(btrim(r.treatment_text),'') <> '' THEN
      r.treatment_text || ' > ' ||
      coalesce(nullif(btrim(r.marker_rollup_display_fluortag),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(r.marker_rollup_display_fluortag),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
  END AS tx_gt_fluortag,

  CASE
    WHEN coalesce(btrim(r.treatment_text),'') <> '' THEN
      r.treatment_text || ' > ' ||
      coalesce(nullif(btrim(r.marker_rollup_display_fluororganelle),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(r.marker_rollup_display_fluororganelle),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
  END AS tx_gt_fluororganelle,

  -- Back-compat aliases (some page versions used display_*)
  CASE
    WHEN coalesce(btrim(r.treatment_text),'') <> '' THEN
      r.treatment_text || ' > ' ||
      coalesce(nullif(btrim(r.marker_rollup_display_tg),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(r.marker_rollup_display_tg),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
  END AS display_tg,

  CASE
    WHEN coalesce(btrim(r.treatment_text),'') <> '' THEN
      r.treatment_text || ' > ' ||
      coalesce(nullif(btrim(r.marker_rollup_display_fluortag),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(r.marker_rollup_display_fluortag),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
  END AS display_fluortag,

  CASE
    WHEN coalesce(btrim(r.treatment_text),'') <> '' THEN
      r.treatment_text || ' > ' ||
      coalesce(nullif(btrim(r.marker_rollup_display_fluororganelle),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(r.marker_rollup_display_fluororganelle),''), nullif(btrim(r.genotype_pretty),''), nullif(btrim(r.genotype_basecodes),''), '')
  END AS display_fluororganelle

FROM public.v_roi_overview_rollups r;

COMMIT;
