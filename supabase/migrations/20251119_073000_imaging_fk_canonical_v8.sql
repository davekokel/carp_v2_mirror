BEGIN;

----------------------------------------------------------------------
-- imaging_slots.plate_id → imaging_plates(id)
----------------------------------------------------------------------

ALTER TABLE public.imaging_slots
  DROP CONSTRAINT IF EXISTS imaging_slots_plate_id_fkey,
  DROP CONSTRAINT IF EXISTS fk_imaging_slots_plate,
  DROP CONSTRAINT IF EXISTS fk_imaging_slots_imaging_plates;

ALTER TABLE public.imaging_slots
  ADD CONSTRAINT fk_imaging_slots_plate
  FOREIGN KEY (plate_id)
  REFERENCES public.imaging_plates(id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

----------------------------------------------------------------------
-- imaging_roi_annotations.slot_id → imaging_slots(id)
----------------------------------------------------------------------

ALTER TABLE public.imaging_roi_annotations
  DROP CONSTRAINT IF EXISTS fk_imaging_rois_slot,
  DROP CONSTRAINT IF EXISTS imaging_roi_annotations_slot_id_fkey;

ALTER TABLE public.imaging_roi_annotations
  ADD CONSTRAINT fk_imaging_rois_slot
  FOREIGN KEY (slot_id)
  REFERENCES public.imaging_slots(id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

----------------------------------------------------------------------
-- imaging_clutch_memberships.clutch_id → clutches(id)
-- imaging_clutch_memberships.slot_id   → imaging_slots(id)
----------------------------------------------------------------------

ALTER TABLE public.imaging_clutch_memberships
  DROP CONSTRAINT IF EXISTS imaging_clutch_memberships_clutch_id_fkey,
  DROP CONSTRAINT IF EXISTS imaging_clutch_memberships_slot_id_fkey,
  DROP CONSTRAINT IF EXISTS fk_icm_clutch,
  DROP CONSTRAINT IF EXISTS fk_icm_slot;

ALTER TABLE public.imaging_clutch_memberships
  ADD CONSTRAINT fk_icm_clutch
  FOREIGN KEY (clutch_id)
  REFERENCES public.clutches(id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE public.imaging_clutch_memberships
  ADD CONSTRAINT fk_icm_slot
  FOREIGN KEY (slot_id)
  REFERENCES public.imaging_slots(id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

COMMIT;
