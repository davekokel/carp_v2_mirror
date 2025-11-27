BEGIN;

DROP VIEW IF EXISTS public.v_roi_overview;

CREATE VIEW public.v_roi_overview AS
SELECT
  ra.id::text               AS roi_id,
  p.plate_code,
  p.experiment_date,
  p.experiment_name,
  p.scope_name,
  p.scope_settings,
  p.plate_note,
  s.slot_label,
  s.slot_index,
  s.slot_note,
  ra.roi_index_within_slot,
  ra.roi_code,
  ra.roi_note_anatomy,
  ra.roi_path,
  ra.created_at
FROM public.imaging_roi_annotations AS ra
JOIN public.imaging_slots AS s
  ON s.id = ra.slot_id
JOIN public.imaging_plates AS p
  ON p.id = s.plate_id
ORDER BY
  p.plate_code,
  s.slot_label,
  ra.roi_index_within_slot,
  ra.id;

COMMIT;
