BEGIN;

CREATE TABLE IF NOT EXISTS public.roi_notes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  roi_id uuid NOT NULL REFERENCES public.imaging_rois(id) ON DELETE CASCADE,
  note_text text NOT NULL,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
