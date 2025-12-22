BEGIN;

CREATE OR REPLACE VIEW public.v_roi_overview_display_v6 AS
WITH base AS (
  SELECT
    ps.experiment_date,
    ps.experiment_name,
    r.roi_code,
    r.roi_path,
    ps.clutch_code,
    tg.treated_clutch_code,
    ps.treat_code AS treatment_code,
    ps.treat_text AS treatment_text,
    g.genotype_basecodes,
    ps.genotype_pretty,
    ps.plate_code,
    ps.slot_index,
    ps.slot_label,
    r.roi_index_within_slot,

    NULL::text AS genotype_tg_style,
    NULL::text AS genotype_fluortag_style,
    NULL::text AS genotype_fluororganelle_style,

    tg.treatment_label_tg_style AS label_tg_style,
    tg.treatment_label_fluortag_style AS label_fluortag_style,
    tg.treatment_label_fluororganelle_style AS label_fluororganelle_style,

    NULLIF(btrim(tg.treatment_label_tg_style), '') AS marker_rollup_display_tg,
    NULLIF(btrim(tg.treatment_label_fluortag_style), '') AS marker_rollup_display_fluortag,
    NULLIF(btrim(tg.treatment_label_fluororganelle_style), '') AS marker_rollup_display_fluororganelle,

    r.created_at,
    r.roi_note_anatomy,
    ps.plate_note,
    ps.slot_note,
    ps.slot_orientation
  FROM public.imaging_roi_annotations r
  LEFT JOIN public.v11_imaging_plate_slot_overview ps
    ON ps.slot_id::uuid = r.slot_id
  LEFT JOIN public.genotypes_v11 g
    ON g.genotype_code = ps.genotype_code
  LEFT JOIN public.v11_treated_clutch_genotype_star_labels tg
    ON tg.genotype_code = ps.genotype_code
),
pretty_by_treatment AS (
  SELECT
    t.treat_code AS treatment_code,
    TRIM(BOTH ';' FROM concat_ws('; ',
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'plasmid') > 0
          THEN ('plasmid(' || string_agg(DISTINCT c.base_code, '; ' ORDER BY c.base_code) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'plasmid') || ')')
        ELSE NULL
      END,
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'rna') > 0
          THEN ('rna(' || string_agg(DISTINCT c.base_code, '; ' ORDER BY c.base_code) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'rna') || ')')
        ELSE NULL
      END,
      CASE
        WHEN count(DISTINCT d.code) > 0
          THEN ('dye(' || string_agg(DISTINCT lower(d.code), '; ' ORDER BY lower(d.code)) || ')')
        ELSE NULL
      END
    )) AS treatment_pretty_tg,
    TRIM(BOTH ';' FROM concat_ws('; ',
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'plasmid') > 0
          THEN ('plasmid(' || string_agg(DISTINCT v.fusion_pretty, '; ' ORDER BY v.fusion_pretty) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'plasmid') || ')')
        ELSE NULL
      END,
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'rna') > 0
          THEN ('rna(' || string_agg(DISTINCT v.fusion_pretty, '; ' ORDER BY v.fusion_pretty) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'rna') || ')')
        ELSE NULL
      END,
      CASE
        WHEN count(DISTINCT d.code) > 0
          THEN ('dye(' || string_agg(DISTINCT lower(d.code), '; ' ORDER BY lower(d.code)) || ')')
        ELSE NULL
      END
    )) AS treatment_pretty_fluortag,
    TRIM(BOTH ';' FROM concat_ws('; ',
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'plasmid') > 0
          THEN ('plasmid(' || string_agg(DISTINCT v.organelle_fluors, '; ' ORDER BY v.organelle_fluors) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'plasmid') || ')')
        ELSE NULL
      END,
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'rna') > 0
          THEN ('rna(' || string_agg(DISTINCT v.organelle_fluors, '; ' ORDER BY v.organelle_fluors) FILTER (WHERE lower(COALESCE(tmc.delivery_form, '')) = 'rna') || ')')
        ELSE NULL
      END,
      CASE
        WHEN count(DISTINCT d.code) > 0
          THEN ('dye(' || string_agg(DISTINCT lower(d.code), '; ' ORDER BY lower(d.code)) || ')')
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
  b.experiment_date,
  b.experiment_name,
  b.roi_code,
  b.roi_path,
  b.clutch_code,
  b.treated_clutch_code,
  b.treatment_code,
  b.treatment_text,
  b.genotype_basecodes,
  b.genotype_pretty,
  b.plate_code,
  b.slot_index,
  b.slot_label,
  b.roi_index_within_slot,
  b.genotype_tg_style,
  b.genotype_fluortag_style,
  b.genotype_fluororganelle_style,
  b.label_tg_style,
  b.label_fluortag_style,
  b.label_fluororganelle_style,
  b.marker_rollup_display_tg,
  b.marker_rollup_display_fluortag,
  b.marker_rollup_display_fluororganelle,
  b.created_at,
  b.roi_note_anatomy,
  b.plate_note,
  b.slot_note,

  CASE
    WHEN COALESCE(btrim(b.treatment_text), '') <> '' THEN
      CASE WHEN COALESCE(btrim(b.marker_rollup_display_tg), '') <> '' THEN (b.treatment_text || ' > ' || b.marker_rollup_display_tg) ELSE NULL END
    ELSE NULLIF(btrim(b.marker_rollup_display_tg), '')
  END AS display_tg,

  CASE
    WHEN COALESCE(btrim(b.treatment_text), '') <> '' THEN
      CASE WHEN COALESCE(btrim(b.marker_rollup_display_fluortag), '') <> '' THEN (b.treatment_text || ' > ' || b.marker_rollup_display_fluortag) ELSE NULL END
    ELSE NULLIF(btrim(b.marker_rollup_display_fluortag), '')
  END AS display_fluortag,

  CASE
    WHEN COALESCE(btrim(b.treatment_text), '') <> '' THEN
      CASE WHEN COALESCE(btrim(b.marker_rollup_display_fluororganelle), '') <> '' THEN (b.treatment_text || ' > ' || b.marker_rollup_display_fluororganelle) ELSE NULL END
    ELSE NULLIF(btrim(b.marker_rollup_display_fluororganelle), '')
  END AS display_fluororganelle,

  CASE
    WHEN COALESCE(btrim(COALESCE(p.treatment_pretty_tg, '')), '') <> '' THEN
      CASE WHEN COALESCE(btrim(b.marker_rollup_display_tg), '') <> '' THEN (p.treatment_pretty_tg || ' > ' || b.marker_rollup_display_tg) ELSE NULL END
    ELSE NULLIF(btrim(b.marker_rollup_display_tg), '')
  END AS tx_gt_tg,

  CASE
    WHEN COALESCE(btrim(COALESCE(p.treatment_pretty_fluortag, '')), '') <> '' THEN
      CASE WHEN COALESCE(btrim(b.marker_rollup_display_fluortag), '') <> '' THEN (p.treatment_pretty_fluortag || ' > ' || b.marker_rollup_display_fluortag) ELSE NULL END
    ELSE NULLIF(btrim(b.marker_rollup_display_fluortag), '')
  END AS tx_gt_fluortag,

  CASE
    WHEN COALESCE(btrim(COALESCE(p.treatment_pretty_fluororganelle, '')), '') <> '' THEN
      CASE WHEN COALESCE(btrim(b.marker_rollup_display_fluororganelle), '') <> '' THEN (p.treatment_pretty_fluororganelle || ' > ' || b.marker_rollup_display_fluororganelle) ELSE NULL END
    ELSE NULLIF(btrim(b.marker_rollup_display_fluororganelle), '')
  END AS tx_gt_fluororganelle,

  b.slot_orientation
FROM base b
LEFT JOIN pretty_by_treatment p
  ON p.treatment_code = b.treatment_code;

COMMIT;
