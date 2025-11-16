CREATE TABLE IF NOT EXISTS public.crosses (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cross_run_code text UNIQUE,
  female_fish_id uuid NOT NULL
    REFERENCES public.fish_instance(id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  male_fish_id   uuid NOT NULL
    REFERENCES public.fish_instance(id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  cross_date     date,
  notes          text,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crosses_female_fish_id
  ON public.crosses (female_fish_id);

CREATE INDEX IF NOT EXISTS idx_crosses_male_fish_id
  ON public.crosses (male_fish_id);

CREATE TABLE IF NOT EXISTS public.clutches (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cross_id            uuid NOT NULL
    REFERENCES public.crosses(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  clutch_date         date NOT NULL,
  clutch_code         text,
  estimated_egg_count integer,
  notes               text,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clutches_cross_id
  ON public.clutches (cross_id);
