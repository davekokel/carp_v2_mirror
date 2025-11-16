BEGIN;

CREATE TABLE IF NOT EXISTS public.tanks (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_code   text UNIQUE NOT NULL,
  location    text,
  status      text,
  volume_l    numeric,
  notes       text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tank_memberships (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_id     uuid NOT NULL
    REFERENCES public.tanks(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  fish_id     uuid NOT NULL
    REFERENCES public.fish_instance(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  role        text,
  started_at  timestamptz NOT NULL,
  ended_at    timestamptz,
  notes       text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tank_memberships_tank_id
  ON public.tank_memberships (tank_id);

CREATE INDEX IF NOT EXISTS idx_tank_memberships_fish_id
  ON public.tank_memberships (fish_id);

CREATE TABLE IF NOT EXISTS public.tank_pairs (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_id        uuid NOT NULL
    REFERENCES public.tanks(id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  female_fish_id uuid NOT NULL
    REFERENCES public.fish_instance(id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  male_fish_id   uuid NOT NULL
    REFERENCES public.fish_instance(id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  active_from    timestamptz NOT NULL,
  active_until   timestamptz,
  notes          text,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tank_pairs_tank_id
  ON public.tank_pairs (tank_id);

CREATE INDEX IF NOT EXISTS idx_tank_pairs_female_fish_id
  ON public.tank_pairs (female_fish_id);

CREATE INDEX IF NOT EXISTS idx_tank_pairs_male_fish_id
  ON public.tank_pairs (male_fish_id);

ALTER TABLE public.crosses
  ADD COLUMN IF NOT EXISTS tank_pair_id uuid;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.crosses'::regclass
      AND conname  = 'fk_crosses_tank_pair'
  ) THEN
    ALTER TABLE public.crosses
      ADD CONSTRAINT fk_crosses_tank_pair
      FOREIGN KEY (tank_pair_id)
      REFERENCES public.tank_pairs(id)
      ON UPDATE CASCADE ON DELETE SET NULL;
  END IF;
END$$;

COMMIT;
