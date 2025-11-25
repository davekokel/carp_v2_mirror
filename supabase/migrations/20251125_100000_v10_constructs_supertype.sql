BEGIN;

CREATE TABLE public.constructs (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  construct_type  text NOT NULL,
  base_code       text NOT NULL,
  name            text NOT NULL,
  nickname        text,
  description     text,
  created_at      timestamptz NOT NULL DEFAULT now(),

  CHECK (construct_type IN ('plasmid','rna','crispr')),
  UNIQUE (base_code),
  UNIQUE (construct_type, base_code)
);

ALTER TABLE public.plasmids
  ADD COLUMN construct_id uuid;

ALTER TABLE public.rnas
  ADD COLUMN construct_id uuid;

ALTER TABLE public.crisprs
  ADD COLUMN construct_id uuid;

COMMIT;
