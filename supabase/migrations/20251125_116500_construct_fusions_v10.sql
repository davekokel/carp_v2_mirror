BEGIN;

CREATE TABLE IF NOT EXISTS public.construct_fusions (
  construct_id uuid NOT NULL REFERENCES public.constructs(id) ON DELETE CASCADE,
  fusion_id    uuid NOT NULL REFERENCES public.fusions(id) ON DELETE RESTRICT,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (construct_id, fusion_id)
);

COMMIT;
