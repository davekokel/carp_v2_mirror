BEGIN;

-- STRICT: requires these views to exist right now.
DROP VIEW public.v_roi_overview_rollups CASCADE;

CREATE VIEW public.v_roi_overview_rollups AS
SELECT
  vo.experiment_date,
  vo.experiment_name,

  vo.roi_code,
  vo.roi_path,

  vo.clutch_code,
  vo.treated_clutch_code,
  vo.treatment_code,
  vo.treatment_text,

  vo.genotype_basecodes,
  vo.genotype_pretty,

  vo.plate_code,
  vo.slot_index,
  vo.slot_label,
  vo.roi_index_within_slot,

  vo.genotype_tg_style,
  vo.genotype_fluortag_style,
  vo.genotype_fluororganelle_style,

  vo.label_tg_style,
  vo.label_fluortag_style,
  vo.label_fluororganelle_style,

  coalesce(nullif(btrim(vo.label_tg_style),''), nullif(btrim(vo.genotype_tg_style),'')) AS marker_rollup_display_tg,
  coalesce(nullif(btrim(vo.label_fluortag_style),''), nullif(btrim(vo.genotype_fluortag_style),'')) AS marker_rollup_display_fluortag,
  coalesce(nullif(btrim(vo.label_fluororganelle_style),''), nullif(btrim(vo.genotype_fluororganelle_style),'')) AS marker_rollup_display_fluororganelle,

  vo.created_at,
  vo.roi_note_anatomy,
  vo.plate_note,
  vo.slot_note
FROM public.v_roi_overview vo;

-- STRICT: requires this view to exist right now (it was dropped by CASCADE above).
CREATE VIEW public.v_roi_overview_rollups_qc AS
SELECT
  count(*) AS n_rollups,
  count(*) FILTER (WHERE coalesce(btrim(marker_rollup_display_fluortag),'') <> '') AS n_with_rollup_fluortag,
  count(*) FILTER (WHERE coalesce(btrim(marker_rollup_display_fluororganelle),'') <> '') AS n_with_rollup_fluororganelle,
  count(*) FILTER (
    WHERE coalesce(btrim(marker_rollup_display_tg),'') <> ''
      AND coalesce(btrim(marker_rollup_display_fluortag),'') = ''
  ) AS n_tg_present_but_fluortag_blank
FROM public.v_roi_overview_rollups;

COMMIT;
