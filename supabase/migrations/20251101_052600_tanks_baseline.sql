BEGIN;

CREATE TABLE IF NOT EXISTS public.tanks (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_code   text UNIQUE NOT NULL,
  status      text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tank_pairs (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_pair_code   text UNIQUE NOT NULL,
  mother_tank_id   uuid REFERENCES public.tanks(id) ON DELETE SET NULL,
  father_tank_id   uuid REFERENCES public.tanks(id) ON DELETE SET NULL,
  created_at       timestamptz NOT NULL DEFAULT now()
);

COMMIT;
