BEGIN;

CREATE TABLE IF NOT EXISTS public.clutch_annotations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_id   uuid NOT NULL REFERENCES public.clutches(id) ON DELETE CASCADE,
  kind_code   text NOT NULL,
  value_num   numeric,
  value_text  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  created_by  text
);

CREATE INDEX IF NOT EXISTS idx_clutch_annotations_clutch_id
  ON public.clutch_annotations (clutch_id);

CREATE INDEX IF NOT EXISTS idx_clutch_annotations_clutch_kind_created_at
  ON public.clutch_annotations (clutch_id, kind_code, created_at);

COMMIT;
