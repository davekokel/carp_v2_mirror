BEGIN;

ALTER TABLE public.imaging_roi_annotations
  ADD COLUMN fish_instance_id uuid NULL;

ALTER TABLE public.imaging_roi_annotations
  ADD CONSTRAINT imaging_roi_annotations_fish_instance_fk
  FOREIGN KEY (fish_instance_id)
  REFERENCES public.fish_instances_v10(id);

CREATE INDEX IF NOT EXISTS imaging_roi_annotations_fish_instance_idx
  ON public.imaging_roi_annotations (fish_instance_id);

COMMIT;
