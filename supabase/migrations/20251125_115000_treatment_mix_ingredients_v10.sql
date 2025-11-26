BEGIN;

-- Drop the old polymorphic mix_ingredients table if it still exists
DROP TABLE IF EXISTS public.mix_ingredients CASCADE;

-- 1) Constructs in a mix
CREATE TABLE public.treatment_mix_constructs (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  mix_id       uuid NOT NULL REFERENCES public.treatment_mixes(id) ON DELETE CASCADE,
  construct_id uuid NOT NULL REFERENCES public.constructs(id) ON DELETE RESTRICT,
  amount_pg    numeric,                -- amount of DNA/RNA in pg
  units        text,                   -- optional override, e.g. 'ng', 'µg'
  role         text,                   -- e.g. 'cargo', 'helper', 'control'
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_treatment_mix_constructs_mix_id
  ON public.treatment_mix_constructs (mix_id);

CREATE INDEX idx_treatment_mix_constructs_construct_id
  ON public.treatment_mix_constructs (construct_id);

-- 2) Dyes in a mix
CREATE TABLE public.treatment_mix_dyes (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  mix_id          uuid NOT NULL REFERENCES public.treatment_mixes(id) ON DELETE CASCADE,
  dye_id          uuid NOT NULL REFERENCES public.dyes(id) ON DELETE RESTRICT,
  concentration_uM numeric,          -- final concentration in µM
  units           text,              -- optional override
  role            text,              -- e.g. 'tracker', 'control'
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_treatment_mix_dyes_mix_id
  ON public.treatment_mix_dyes (mix_id);

CREATE INDEX idx_treatment_mix_dyes_dye_id
  ON public.treatment_mix_dyes (dye_id);

COMMIT;
