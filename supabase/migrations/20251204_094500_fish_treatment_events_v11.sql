BEGIN;

-- ─────────────────────────────────────────────
-- fish_treatment_events_v11 — per-fish treatments / injections
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.fish_treatment_events_v11 (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_instance_id    uuid NOT NULL,
  treatment_id        uuid NULL,
  treatment_kind      text NOT NULL,
  construct_base_code text NULL,
  method              text NULL,
  at_time             timestamptz NULL,
  at_stage            text NULL,
  notes               text NULL,
  created_at          timestamptz NOT NULL DEFAULT now(),
  created_by          text NULL
);

-- FK: fish_instance_id → fish_instances_v10(id)
ALTER TABLE public.fish_treatment_events_v11
  ADD CONSTRAINT fk_fish_treatment_events_fish_instance
  FOREIGN KEY (fish_instance_id)
  REFERENCES public.fish_instances_v10(id)
  ON DELETE CASCADE;

-- FK: treatment_id → treatments(id)
ALTER TABLE public.fish_treatment_events_v11
  ADD CONSTRAINT fk_fish_treatment_events_treatment
  FOREIGN KEY (treatment_id)
  REFERENCES public.treatments(id)
  ON DELETE SET NULL;

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_fish_treatment_events_fish_instance_id
  ON public.fish_treatment_events_v11(fish_instance_id);

CREATE INDEX IF NOT EXISTS idx_fish_treatment_events_treatment_id
  ON public.fish_treatment_events_v11(treatment_id);

COMMIT;
