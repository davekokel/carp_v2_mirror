-- v11: link individual fish instances to treatments (e.g. injection mixes)
BEGIN;

CREATE TABLE IF NOT EXISTS public.join_fish_treatments (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_instance_id uuid NOT NULL REFERENCES public.fish_instances_v10(id) ON DELETE CASCADE,
  treatment_id     uuid NOT NULL REFERENCES public.treatments(id)         ON DELETE RESTRICT,
  created_at       timestamptz NOT NULL DEFAULT now(),
  notes            text
);

CREATE UNIQUE INDEX IF NOT EXISTS join_fish_treatments_fish_treatment_key
  ON public.join_fish_treatments (fish_instance_id, treatment_id);

COMMIT;
