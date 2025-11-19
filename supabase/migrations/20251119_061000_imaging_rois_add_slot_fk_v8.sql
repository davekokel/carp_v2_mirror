BEGIN;

-- Add slot_id column if missing
ALTER TABLE public.imaging_roi_annotations
ADD COLUMN IF NOT EXISTS slot_id uuid;

-- Backfill slot_id from (plate_id_filled, slot_id_filled) via imaging_plates/slots
UPDATE public.imaging_roi_annotations roi
SET slot_id = s.id
FROM public.imaging_slots s
JOIN public.imaging_plates p ON p.id = s.plate_id
WHERE roi.slot_id IS NULL
  AND roi.plate_id_filled IS NOT NULL
  AND roi.slot_id_filled IS NOT NULL
  AND p.plate_code = roi.plate_id_filled
  AND s.slot_label = roi.slot_id_filled;

-- Enforce FK and (optionally) not-null on slot_id
ALTER TABLE public.imaging_roi_annotations
ADD CONSTRAINT fk_imaging_rois_slot
FOREIGN KEY (slot_id)
REFERENCES public.imaging_slots(id)
ON UPDATE CASCADE ON DELETE RESTRICT;

-- In fully v8 you probably want this:
-- ALTER TABLE public.imaging_roi_annotations
-- ALTER COLUMN slot_id SET NOT NULL;

COMMIT;
