BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS public.treatments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind_code text NOT NULL,
  name text NOT NULL,
  notes text DEFAULT '',
  plasmid_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT treatments_kind_chk CHECK (kind_code IN ('plasmid','rna','dye','drug','other'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_treatments_kind_name_plasmid
  ON public.treatments (kind_code, name, COALESCE(plasmid_code,''));
COMMIT;
