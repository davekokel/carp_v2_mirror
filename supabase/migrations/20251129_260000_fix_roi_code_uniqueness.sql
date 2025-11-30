BEGIN;

-- Drop the WRONG global uniqueness
ALTER TABLE public.imaging_roi_annotations
DROP CONSTRAINT IF EXISTS imaging_roi_annotations_roi_code_unique;

-- Correct per-slot uniqueness:
-- A slot can have ROIs 1,2,3...; codes A01-01, A01-02... but
-- the same codes SHOULD BE allowed on different plates and slots.

ALTER TABLE public.imaging_roi_annotations
ADD CONSTRAINT imaging_roi_annotations_slot_code_unique
    UNIQUE (slot_id, roi_code);

COMMIT;
