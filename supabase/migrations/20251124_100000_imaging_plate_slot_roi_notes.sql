BEGIN;

-- Plate-level fields
ALTER TABLE public.imaging_plates
  ADD COLUMN IF NOT EXISTS scope_name     text,
  ADD COLUMN IF NOT EXISTS scope_settings text,
  ADD COLUMN IF NOT EXISTS plate_note     text;

COMMENT ON COLUMN public.imaging_plates.scope_name
  IS 'Microscope or imaging system name used for this plate (imager-entered).';

COMMENT ON COLUMN public.imaging_plates.scope_settings
  IS 'Free-text description of key imaging settings for this plate (objective, zoom, etc.).';

COMMENT ON COLUMN public.imaging_plates.plate_note
  IS 'General note about this plate (imager-entered).';

-- Slot-level field
ALTER TABLE public.imaging_slots
  ADD COLUMN IF NOT EXISTS slot_note text;

COMMENT ON COLUMN public.imaging_slots.slot_note
  IS 'Per-slot note (e.g. fish/condition notes entered by imager).';

-- ROI-level fields
ALTER TABLE public.imaging_roi_annotations
  ADD COLUMN IF NOT EXISTS roi_path         text,
  ADD COLUMN IF NOT EXISTS roi_note_anatomy text;

COMMENT ON COLUMN public.imaging_roi_annotations.roi_path
  IS 'Path or identifier for this ROI image; required for modern imaging data.';

COMMENT ON COLUMN public.imaging_roi_annotations.roi_note_anatomy
  IS 'Free-text anatomical note for this ROI (imager-entered).';

COMMIT;
