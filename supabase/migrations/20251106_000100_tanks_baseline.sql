BEGIN;

CREATE TABLE IF NOT EXISTS public.locations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code        text UNIQUE NOT NULL,
  name        text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tanks (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_code   text UNIQUE NOT NULL,
  location_id uuid REFERENCES public.locations(id) ON DELETE SET NULL,
  status      text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tank_pairs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_pair_code  text UNIQUE NOT NULL,
  mother_tank_id  uuid REFERENCES public.tanks(id) ON DELETE SET NULL,
  father_tank_id  uuid REFERENCES public.tanks(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  t.id           AS tank_uuid,
  t.tank_code    AS tank_code,
  COALESCE(l.code,'') AS location_code,
  COALESCE(t.status,'') AS status,
  t.created_at
FROM public.tanks t
LEFT JOIN public.locations l ON l.id=t.location_id;

CREATE OR REPLACE VIEW public.v_tank_pairs AS
SELECT
  tp.tank_pair_code,
  m.tank_code AS tank_code_female,
  f.tank_code AS tank_code_male,
  tp.created_at
FROM public.tank_pairs tp
LEFT JOIN public.tanks m ON m.id = tp.mother_tank_id
LEFT JOIN public.tanks f ON f.id = tp.father_tank_id;

COMMIT;
