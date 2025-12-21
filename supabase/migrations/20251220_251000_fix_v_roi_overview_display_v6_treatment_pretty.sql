BEGIN;

DROP VIEW IF EXISTS public.v_roi_overview_display_v6;

CREATE VIEW public.v_roi_overview_display_v6 AS
WITH base AS (
  SELECT r.*
  FROM public.v_roi_overview_rollups r
),
pretty_by_treatment AS (
  SELECT
    t.treat_code AS treatment_code,

    -- TG style: base_code(s)
    trim(both ';' from concat_ws(
      '; ',
      CASE
        WHEN count(*) FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'plasmid') > 0
          THEN 'plasmid(' ||
               string_agg(DISTINCT c.base_code, '; ' ORDER BY c.base_code)
               FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'plasmid') || ')'
        ELSE NULL
      END,
      CASE
        WHEN count(*) FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'rna') > 0
          THEN 'rna(' ||
               string_agg(DISTINCT c.base_code, '; ' ORDER BY c.base_code)
               FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'rna') || ')'
        ELSE NULL
      END,
      CASE
        WHEN count(DISTINCT d.code) > 0
          THEN 'dye(' || string_agg(DISTINCT lower(d.code), '; ' ORDER BY lower(d.code)) || ')'
        ELSE NULL
      END
    )) AS treatment_pretty_tg,

    -- Fluortag style: fusion_pretty
    trim(both ';' from concat_ws(
      '; ',
      CASE
        WHEN count(*) FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'plasmid') > 0
          THEN 'plasmid(' ||
               string_agg(DISTINCT v.fusion_pretty, '; ' ORDER BY v.fusion_pretty)
               FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'plasmid') || ')'
        ELSE NULL
      END,
      CASE
        WHEN count(*) FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'rna') > 0
          THEN 'rna(' ||
               string_agg(DISTINCT v.fusion_pretty, '; ' ORDER BY v.fusion_pretty)
               FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'rna') || ')'
        ELSE NULL
      END,
      CASE
        WHEN count(DISTINCT d.code) > 0
          THEN 'dye(' || string_agg(DISTINCT lower(d.code), '; ' ORDER BY lower(d.code)) || ')'
        ELSE NULL
      END
    )) AS treatment_pretty_fluortag,

    -- Fluororganelle style: organelle_fluors
    trim(both ';' from concat_ws(
      '; ',
      CASE
        WHEN count(*) FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'plasmid') > 0
          THEN 'plasmid(' ||
               string_agg(DISTINCT v.organelle_fluors, '; ' ORDER BY v.organelle_fluors)
               FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'plasmid') || ')'
        ELSE NULL
      END,
      CASE
        WHEN count(*) FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'rna') > 0
          THEN 'rna(' ||
               string_agg(DISTINCT v.organelle_fluors, '; ' ORDER BY v.organelle_fluors)
               FILTER (WHERE lower(coalesce(tmc.delivery_form,'')) = 'rna') || ')'
        ELSE NULL
      END,
      CASE
        WHEN count(DISTINCT d.code) > 0
          THEN 'dye(' || string_agg(DISTINCT lower(d.code), '; ' ORDER BY lower(d.code)) || ')'
        ELSE NULL
      END
    )) AS treatment_pretty_fluororganelle

  FROM public.treatments t
  LEFT JOIN public.treatment_mixes tm ON tm.treatment_id = t.id
  LEFT JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
  LEFT JOIN public.constructs c ON c.id = tmc.construct_id
  LEFT JOIN public.v_constructs_overview v ON lower(v.construct_code) = lower(c.base_code)
  LEFT JOIN public.treatment_mix_dyes tmd ON tmd.mix_id = tm.id
  LEFT JOIN public.dyes d ON d.id = tmd.dye_id
  GROUP BY t.treat_code
)
SELECT
  b.*,

  CASE
    WHEN coalesce(btrim(b.treatment_text),'') <> '' THEN
      b.treatment_text || ' > ' ||
      coalesce(nullif(btrim(b.marker_rollup_display_tg),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(b.marker_rollup_display_tg),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
  END AS display_tg,

  CASE
    WHEN coalesce(btrim(b.treatment_text),'') <> '' THEN
      b.treatment_text || ' > ' ||
      coalesce(nullif(btrim(b.marker_rollup_display_fluortag),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(b.marker_rollup_display_fluortag),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
  END AS display_fluortag,

  CASE
    WHEN coalesce(btrim(b.treatment_text),'') <> '' THEN
      b.treatment_text || ' > ' ||
      coalesce(nullif(btrim(b.marker_rollup_display_fluororganelle),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(b.marker_rollup_display_fluororganelle),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
  END AS display_fluororganelle,

  CASE
    WHEN coalesce(btrim(coalesce(p.treatment_pretty_tg,'')),'') <> '' THEN
      p.treatment_pretty_tg || ' > ' ||
      coalesce(nullif(btrim(b.marker_rollup_display_tg),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(b.marker_rollup_display_tg),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
  END AS tx_gt_tg,

  CASE
    WHEN coalesce(btrim(coalesce(p.treatment_pretty_fluortag,'')),'') <> '' THEN
      p.treatment_pretty_fluortag || ' > ' ||
      coalesce(nullif(btrim(b.marker_rollup_display_fluortag),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(b.marker_rollup_display_fluortag),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
  END AS tx_gt_fluortag,

  CASE
    WHEN coalesce(btrim(coalesce(p.treatment_pretty_fluororganelle,'')),'') <> '' THEN
      p.treatment_pretty_fluororganelle || ' > ' ||
      coalesce(nullif(btrim(b.marker_rollup_display_fluororganelle),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
    ELSE
      coalesce(nullif(btrim(b.marker_rollup_display_fluororganelle),''), nullif(btrim(b.genotype_pretty),''), nullif(btrim(b.genotype_basecodes),''), '')
  END AS tx_gt_fluororganelle

FROM base b
LEFT JOIN pretty_by_treatment p ON p.treatment_code = b.treatment_code;

COMMIT;
