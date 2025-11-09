BEGIN;
ALTER TABLE public.dyes ADD COLUMN IF NOT EXISTS localization text;
CREATE TABLE IF NOT EXISTS public.dye_tag_targets (
  dye_id uuid NOT NULL REFERENCES public.dyes(id) ON DELETE CASCADE,
  tag_id uuid NOT NULL REFERENCES public.tags(id) ON DELETE CASCADE,
  note   text,
  PRIMARY KEY (dye_id, tag_id)
);
COMMIT;
