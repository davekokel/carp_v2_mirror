BEGIN;

DROP VIEW IF EXISTS public.v_imaging_clutches_rois;

CREATE VIEW public.v_imaging_clutches_rois AS
SELECT
  c.clutch_code,
  c.clutch_date,
  c.estimated_egg_count,
  m.id::text        AS membership_id,
  m.role            AS membership_role,
  m.embryo_count,
  m.mount_notes,
  m.created_at      AS membership_created_at,
  p.plate_code,
  s.slot_label,
  ra.roi_code,
  ra.roi_index_within_slot AS roi_index,
  ra.roi_path       AS data_path
FROM public.imaging_clutch_memberships AS m
JOIN public.clutches AS c
  ON c.id = m.clutch_id
JOIN public.imaging_slots AS s
  ON s.id = m.slot_id
JOIN public.imaging_plates AS p
  ON p.id = s.plate_id
LEFT JOIN public.imaging_roi_annotations AS ra
  ON ra.slot_id = s.id
ORDER BY
  c.clutch_code,
  p.plate_code,
  s.slot_label,
  ra.roi_index_within_slot,
  ra.id;

COMMIT;
