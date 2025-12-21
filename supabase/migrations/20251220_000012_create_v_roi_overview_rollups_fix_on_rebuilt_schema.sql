create or replace view public.v_roi_overview_rollups_fix as
select
  b.experiment_date,
  b.experiment_name,
  b.roi_code,
  b.roi_path,
  b.clutch_code,

  coalesce(tc.treated_clutch_code, ''::text) as treated_clutch_code,

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
  b.slot_note
from public.v_roi_overview_rollups b
left join public.imaging_roi_annotations ira
  on ira.roi_code = b.roi_code
left join public.imaging_clutch_memberships m
  on m.slot_id = ira.slot_id
left join public.treated_clutches_v11 tc
  on tc.id = m.treated_clutch_id;
