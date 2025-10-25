BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Minimal fish table
CREATE TABLE IF NOT EXISTS public.fish (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_code   text NOT NULL,
  name        text,
  nickname    text,
  genetic_background  text,
  line_building_stage text,
  date_birth  date,
  created_by  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Uniques / safety if table pre-existed
CREATE UNIQUE INDEX IF NOT EXISTS uq_fish_code ON public.fish(fish_code);

-- Minimal tanks table
CREATE TABLE IF NOT EXISTS public.tanks (
  tank_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tank_code   text NOT NULL,
  fish_code   text,                    -- loose FK by code; later migrations may tighten
  rack        text,
  position    text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  created_by  uuid,
  -- include these so later scripts that reference them won't fail if they add/alter
  tank_uuid   uuid DEFAULT gen_random_uuid(),
  status      text DEFAULT 'active'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tanks_code  ON public.tanks(tank_code);

COMMIT;
