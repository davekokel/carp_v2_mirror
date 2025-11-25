BEGIN;

CREATE TABLE public.treatment_mixes (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  treatment_id  uuid NOT NULL REFERENCES public.treatments(id) ON DELETE CASCADE,
  mix_code      text NOT NULL,
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.mix_ingredients (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  mix_id          uuid NOT NULL REFERENCES public.treatment_mixes(id) ON DELETE CASCADE,
  ingredient_type text NOT NULL,
  ingredient_id   uuid NOT NULL,
  concentration   text,
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

COMMIT;
