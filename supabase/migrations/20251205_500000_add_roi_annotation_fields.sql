BEGIN;

ALTER TABLE public.imaging_roi_annotations
    ADD COLUMN IF NOT EXISTS annotation_notes text,
    ADD COLUMN IF NOT EXISTS qc_flag text;

COMMENT ON COLUMN public.imaging_roi_annotations.annotation_notes IS
'User-entered notes for ROI annotation (free text)';

COMMENT ON COLUMN public.imaging_roi_annotations.qc_flag IS
'QC flag per ROI (free text; user-defined)';

COMMIT;
