BEGIN;

DROP VIEW IF EXISTS public.v11_imaging_roi_star;

CREATE VIEW public.v11_imaging_roi_star AS
SELECT
  ra.id::text                       AS roi_id,
  ra.roi_code,
  ra.roi_index_within_slot          AS roi_index,
  ra.roi_path,
  ra.roi_note_anatomy,
  ra.created_at                     AS roi_created_at,
  p.id::text                        AS plate_id,
  p.plate_code,
  p.experiment_date,
  p.experiment_name,
  p.scope_name,
  p.scope_settings,
  p.plate_note,
  s.id::text                        AS slot_id,
  s.slot_label,
  s.slot_index,
  s.slot_note,
  c.id::text                        AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  c.estimated_egg_count,
  icm.id::text                      AS membership_id,
  icm.role                          AS membership_role,
  icm.embryo_count,
  icm.mount_notes,
  icm.created_at                    AS membership_created_at,
  ra.fish_instance_id,
  fis.fish_code,
  fis.line_instance_code,
  fis.line_code,
  fis.group_code,
  fis.line_nickname,
  fis.genetic_background,
  fis.line_building_stage,
  fis.genotype_pretty               AS fish_genotype_pretty,
  fis.organelle_fluors              AS line_organelle_fluors,
  t.tank_code,
  t.status                          AS tank_status
FROM public.imaging_roi_annotations ra
JOIN public.imaging_slots s
  ON s.id = ra.slot_id
JOIN public.imaging_plates p
  ON p.id = s.id_plate
     OR p.id = s.plate_id           -- keep whichever you actually use
LEFT JOIN public.imaging_clutch_memberships icm
  ON icm.slot_id = s.id
LEFT JOIN public.clutches c
  ON c.id = icm.clutch_id
LEFT JOIN public.v11_fish_instance_star fis
  ON fis.fish_instance_id = ra.fish_instance_id
LEFT JOIN public.tanks t
  ON t.fish_instance_id = ra.fish_instance_id;

COMMIT;
