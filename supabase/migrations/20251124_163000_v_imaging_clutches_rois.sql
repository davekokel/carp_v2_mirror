BEGIN;

DROP VIEW IF EXISTS public.v_imaging_clutches_rois;

CREATE VIEW public.v_imaging_clutches_rois AS
SELECT
  c.clutch_code,
  c.clutch_date,
  c.estimated_egg_count,
  icm.id            AS membership_id,
  icm.role          AS membership_role,
  icm.embryo_count,
  icm.mount_notes,
  icm.created_at    AS membership_created_at,
  p.plate_code,
  s.slot_label,
  v.roi_code,
  v.roi_index_within_slot AS roi_index,
  NULL::text        AS roi_name,
  NULL::text        AS fish_code,
  NULL::text        AS parent_female,
  NULL::text        AS parent_male,
  NULL::date        AS roi_birthday,
  NULL::text        AS all_marker_fluor_codes,
  v.roi_path        AS data_path
FROM public.imaging_clutch_memberships icm
JOIN public.clutches        c ON c.id = icm.clutch_id
JOIN public.imaging_slots   s ON s.id = icm.slot_id
JOIN public.imaging_plates  p ON p.id = s.plate_id
JOIN public.v_roi_overview  v ON v.slot_id = s.id;

COMMIT;
