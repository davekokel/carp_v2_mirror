BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Minimal tank_pairs so code generators can ALTER/trigger later
CREATE TABLE IF NOT EXISTS public.tank_pairs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_pair_code  text,           -- later generator will fill/validate
  fish_pair_code  text,           -- used by code generator to build TP(FP)-NN
  mother_tank_id  uuid,           -- optional; later migrations may firm these up
  father_tank_id  uuid,
  created_by      text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- Optional indexes the later migrations expect/use
CREATE UNIQUE INDEX IF NOT EXISTS uq_tank_pairs_code ON public.tank_pairs(tank_pair_code) WHERE tank_pair_code IS NOT NULL;

COMMIT;
