BEGIN;

-- Drop the old wide table and any dependent views
DROP TABLE IF EXISTS public.imaging_roi_annotations CASCADE;

-- Lean per-ROI table
CREATE TABLE public.imaging_roi_annotations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slot_id uuid NOT NULL REFERENCES public.imaging_slots(id) ON UPDATE CASCADE ON DELETE CASCADE,
  roi_index_within_slot integer NOT NULL,
  roi_code text NOT NULL,
  roi_path text NOT NULL,
  roi_note_anatomy text,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.imaging_roi_annotations IS
  'One row per imaged ROI (modern, lean schema).';

COMMENT ON COLUMN public.imaging_roi_annotations.slot_id IS
  'FK to imaging_slots.id; identifies the well/slot this ROI came from.';

COMMENT ON COLUMN public.imaging_roi_annotations.roi_index_within_slot IS
  '1-based index of this ROI within its slot.';

COMMENT ON COLUMN public.imaging_roi_annotations.roi_code IS
  'Human-readable ROI identifier (e.g. plate:slot:index).';

COMMENT ON COLUMN public.imaging_roi_annotations.roi_path IS
  'Path or identifier for this ROI image; required for modern imaging data.';

COMMENT ON COLUMN public.imaging_roi_annotations.roi_note_anatomy IS
  'Free-text anatomical note for this ROI (imager-entered).';

CREATE UNIQUE INDEX imaging_roi_annotations_slot_idx_unique
  ON public.imaging_roi_annotations (slot_id, roi_index_within_slot);

CREATE UNIQUE INDEX imaging_roi_annotations_roi_code_unique
  ON public.imaging_roi_annotations (roi_code);

-- Clean overview view for UI / analysis
CREATE VIEW public.v_roi_overview AS
SELECT
  ira.id                    AS roi_id,
  ira.roi_code,
  ira.roi_index_within_slot,
  ira.roi_path,
  ira.roi_note_anatomy,
  ira.created_at,

  s.id                      AS slot_id,
  s.slot_index,
  s.slot_label,
  s.slot_note,

  p.id                      AS plate_id,
  p.plate_code,
  p.experiment_date,
  p.experiment_name,
  p.scope_name,
  p.scope_settings,
  p.plate_note
FROM public.imaging_roi_annotations ira
JOIN public.imaging_slots   s ON s.id = ira.slot_id
JOIN public.imaging_plates  p ON p.id = s.plate_id;

COMMENT ON VIEW public.v_roi_overview IS
  'Lean ROI overview joining plates, slots, and per-ROI fields for modern imaging data.';

COMMIT;
