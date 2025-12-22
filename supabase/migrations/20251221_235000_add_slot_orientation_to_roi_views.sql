BEGIN;

-- -------------------------------------------------------------------
-- v11_imaging_plate_slot_overview
-- IMPORTANT: preserve existing 15 columns and APPEND slot_orientation.
-- -------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v11_imaging_plate_slot_overview AS
WITH slot_stats AS (
  SELECT
    s.id AS slot_id,
    count(ira.id) AS n_rois
  FROM public.imaging_slots s
  LEFT JOIN public.imaging_roi_annotations ira
    ON ira.slot_id = s.id
  GROUP BY s.id
),
base AS (
  SELECT
    p.id AS plate_id,
    p.plate_code,
    p.experiment_date,
    COALESCE(p.experiment_name, ''::text) AS experiment_name,
    COALESCE(p.plate_note, ''::text) AS plate_note,
    s.id AS slot_id,
    s.slot_label,
    s.slot_index,
    COALESCE(s.slot_note, ''::text) AS slot_note,
    COALESCE(ss.n_rois, 0::bigint) AS n_rois,
    c.clutch_code,
    t.treat_code,
    t.treat_text,
    g.genotype_code,
    g.genotype_pretty,
    NULLIF(btrim(s.orientation), ''::text) AS slot_orientation
  FROM public.imaging_plates p
  JOIN public.imaging_slots s
    ON s.plate_id = p.id
  LEFT JOIN slot_stats ss
    ON ss.slot_id = s.id
  LEFT JOIN public.imaging_clutch_memberships m
    ON m.slot_id = s.id
  LEFT JOIN public.clutches c
    ON c.id = m.clutch_id
  LEFT JOIN public.treated_clutches_v11 tc
    ON tc.id = m.treated_clutch_id
  LEFT JOIN public.treatments t
    ON t.id = tc.treatment_id
  LEFT JOIN public.genotypes_v11 g
    ON g.id = c.genotype_v11_id
)
SELECT
  plate_id::text AS plate_id,
  plate_code,
  experiment_date,
  experiment_name,
  plate_note,
  slot_id::text AS slot_id,
  slot_label,
  slot_index,
  slot_note,
  n_rois,
  clutch_code,
  treat_code,
  treat_text,
  genotype_code,
  genotype_pretty,
  slot_orientation
FROM base;

-- -------------------------------------------------------------------
-- v_roi_overview
-- IMPORTANT: preserve existing columns and APPEND slot_orientation.
-- -------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_roi_overview AS
SELECT
  r.id::text AS roi_id,
  ps.plate_id,
  ps.plate_code,
  ps.experiment_date,
  ps.experiment_name,
  ps.plate_note,
  ps.slot_id,
  ps.slot_label,
  ps.slot_index,
  ps.slot_note,
  r.roi_index_within_slot,
  r.roi_code,
  r.roi_note_anatomy,
  r.roi_path,
  r.created_at,
  ps.clutch_code,
  tg.treated_clutch_code,
  ps.treat_code AS treatment_code,
  ps.treat_text AS treatment_text,
  ps.genotype_code,
  g.genotype_basecodes,
  ps.genotype_pretty,
  gms.genotype_tg_style,
  gms.genotype_fluortag_style,
  gms.genotype_fluororganelle_style,
  tg.treatment_label_tg_style AS label_tg_style,
  tg.treatment_label_fluortag_style AS label_fluortag_style,
  tg.treatment_label_fluororganelle_style AS label_fluororganelle_style,
  ps.slot_orientation
FROM public.imaging_roi_annotations r
LEFT JOIN public.v11_imaging_plate_slot_overview ps
  ON ps.slot_id::uuid = r.slot_id
LEFT JOIN public.genotypes_v11 g
  ON g.genotype_code = ps.genotype_code
LEFT JOIN public.v11_treated_clutch_genotype_star_labels tg
  ON tg.genotype_code = ps.genotype_code
LEFT JOIN public.v_genotype_marker_styles_strict gms
  ON gms.genotype_code = ps.genotype_code

-- -------------------------------------------------------------------
-- v_roi_overview_rollups (append slot_orientation)
-- -------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_roi_overview_rollups AS
SELECT
  experiment_date,
  experiment_name,
  roi_code,
  roi_path,
  clutch_code,
  treated_clutch_code,
  treatment_code,
  treatment_text,
  genotype_basecodes,
  genotype_pretty,
  plate_code,
  slot_index,
  slot_label,
  roi_index_within_slot,
  genotype_tg_style,
  genotype_fluortag_style,
  genotype_fluororganelle_style,
  label_tg_style,
  label_fluortag_style,
  label_fluororganelle_style,
  COALESCE(NULLIF(btrim(label_tg_style), ''::text), NULLIF(btrim(genotype_tg_style), ''::text)) AS marker_rollup_display_tg,
  COALESCE(NULLIF(btrim(label_fluortag_style), ''::text), NULLIF(btrim(genotype_fluortag_style), ''::text)) AS marker_rollup_display_fluortag,
  COALESCE(NULLIF(btrim(label_fluororganelle_style), ''::text), NULLIF(btrim(genotype_fluororganelle_style), ''::text)) AS marker_rollup_display_fluororganelle,
  created_at,
  roi_note_anatomy,
  plate_note,
  slot_note,
  slot_orientation
FROM public.v_roi_overview vo;

-- -------------------------------------------------------------------
-- v_roi_overview_display_v6 (append slot_orientation)
-- -------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_roi_overview_display_v6 AS
WITH base AS (
  SELECT
    r.experiment_date,
    r.experiment_name,
    r.roi_code,
    r.roi_path,
    r.clutch_code,
    r.treated_clutch_code,
    r.treatment_code,
    r.treatment_text,
    r.genotype_basecodes,
    r.genotype_pretty,
    r.plate_code,
    r.slot_index,
    r.slot_label,
    r.roi_index_within_slot,
    r.genotype_tg_style,
    r.genotype_fluortag_style,
    r.genotype_fluororganelle_style,
    r.label_tg_style,
    r.label_fluortag_style,
    r.label_fluororganelle_style,
    r.marker_rollup_display_tg,
    r.marker_rollup_display_fluortag,
    r.marker_rollup_display_fluororganelle,
    r.created_at,
    r.roi_note_anatomy,
    r.plate_note,
    r.slot_note,
    r.slot_orientation
  FROM public.v_roi_overview_rollups r
),
pretty_by_treatment AS (
  SELECT
    t.treat_code AS treatment_code,
    TRIM(BOTH ';'::text FROM concat_ws('; '::text,
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'plasmid'::text) > 0
          THEN ('plasmid('::text || string_agg(DISTINCT c.base_code, '; '::text ORDER BY c.base_code) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'plasmid'::text)) || ')'::text
        ELSE NULL::text
      END,
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'rna'::text) > 0
          THEN ('rna('::text || string_agg(DISTINCT c.base_code, '; '::text ORDER BY c.base_code) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'rna'::text)) || ')'::text
        ELSE NULL::text
      END,
      CASE
        WHEN count(DISTINCT d.code) > 0
          THEN ('dye('::text || string_agg(DISTINCT lower(d.code), '; '::text ORDER BY (lower(d.code)))) || ')'::text
        ELSE NULL::text
      END
    )) AS treatment_pretty_tg,
    TRIM(BOTH ';'::text FROM concat_ws('; '::text,
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'plasmid'::text) > 0
          THEN ('plasmid('::text || string_agg(DISTINCT v.fusion_pretty, '; '::text ORDER BY v.fusion_pretty) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'plasmid'::text)) || ')'::text
        ELSE NULL::text
      END,
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'rna'::text) > 0
          THEN ('rna('::text || string_agg(DISTINCT v.fusion_pretty, '; '::text ORDER BY v.fusion_pretty) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'rna'::text)) || ')'::text
        ELSE NULL::text
      END,
      CASE
        WHEN count(DISTINCT d.code) > 0
          THEN ('dye('::text || string_agg(DISTINCT lower(d.code), '; '::text ORDER BY (lower(d.code)))) || ')'::text
        ELSE NULL::text
      END
    )) AS treatment_pretty_fluortag,
    TRIM(BOTH ';'::text FROM concat_ws('; '::text,
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'plasmid'::text) > 0
          THEN ('plasmid('::text || string_agg(DISTINCT v.organelle_fluors, '; '::text ORDER BY v.organelle_fluors) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'plasmid'::text)) || ')'::text
        ELSE NULL::text
      END,
      CASE
        WHEN count(*) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'rna'::text) > 0
          THEN ('rna('::text || string_agg(DISTINCT v.organelle_fluors, '; '::text ORDER BY v.organelle_fluors) FILTER (WHERE lower(COALESCE(tmc.delivery_form, ''::text)) = 'rna'::text)) || ')'::text
        ELSE NULL::text
      END,
      CASE
        WHEN count(DISTINCT d.code) > 0
          THEN ('dye('::text || string_agg(DISTINCT lower(d.code), '; '::text ORDER BY (lower(d.code)))) || ')'::text
        ELSE NULL::text
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
    WHEN COALESCE(btrim(b.treatment_text), ''::text) <> ''::text
      THEN (b.treatment_text || ' > '::text) || COALESCE(NULLIF(btrim(b.marker_rollup_display_tg), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
    ELSE COALESCE(NULLIF(btrim(b.marker_rollup_display_tg), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
  END AS display_tg,
  CASE
    WHEN COALESCE(btrim(b.treatment_text), ''::text) <> ''::text
      THEN (b.treatment_text || ' > '::text) || COALESCE(NULLIF(btrim(b.marker_rollup_display_fluortag), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
    ELSE COALESCE(NULLIF(btrim(b.marker_rollup_display_fluortag), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
  END AS display_fluortag,
  CASE
    WHEN COALESCE(btrim(b.treatment_text), ''::text) <> ''::text
      THEN (b.treatment_text || ' > '::text) || COALESCE(NULLIF(btrim(b.marker_rollup_display_fluororganelle), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
    ELSE COALESCE(NULLIF(btrim(b.marker_rollup_display_fluororganelle), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
  END AS display_fluororganelle,
  CASE
    WHEN COALESCE(btrim(COALESCE(p.treatment_pretty_tg, ''::text)), ''::text) <> ''::text
      THEN (p.treatment_pretty_tg || ' > '::text) || COALESCE(NULLIF(btrim(b.marker_rollup_display_tg), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
    ELSE COALESCE(NULLIF(btrim(b.marker_rollup_display_tg), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
  END AS tx_gt_tg,
  CASE
    WHEN COALESCE(btrim(COALESCE(p.treatment_pretty_fluortag, ''::text)), ''::text) <> ''::text
      THEN (p.treatment_pretty_fluortag || ' > '::text) || COALESCE(NULLIF(btrim(b.marker_rollup_display_fluortag), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
    ELSE COALESCE(NULLIF(btrim(b.marker_rollup_display_fluortag), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
  END AS tx_gt_fluortag,
  CASE
    WHEN COALESCE(btrim(COALESCE(p.treatment_pretty_fluororganelle, ''::text)), ''::text) <> ''::text
      THEN (p.treatment_pretty_fluororganelle || ' > '::text) || COALESCE(NULLIF(btrim(b.marker_rollup_display_fluororganelle), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
    ELSE COALESCE(NULLIF(btrim(b.marker_rollup_display_fluororganelle), ''::text), NULLIF(btrim(b.genotype_pretty), ''::text), NULLIF(btrim(b.genotype_basecodes), ''::text), ''::text)
  END AS tx_gt_fluororganelle,
  b.slot_orientation
FROM base b
LEFT JOIN pretty_by_treatment p
  ON p.treatment_code = b.treatment_code;

COMMIT;
