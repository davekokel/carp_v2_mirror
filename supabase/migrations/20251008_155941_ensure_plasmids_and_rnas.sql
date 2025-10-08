BEGIN;

-- plasmids (minimal columns your uploader expects)
CREATE TABLE IF NOT EXISTS public.plasmids (
  id_uuid               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code                  text UNIQUE NOT NULL,
  name                  text,
  nickname              text,
  fluors                text,
  resistance            text,
  supports_invitro_rna  boolean NOT NULL DEFAULT false,
  created_by            text,
  notes                 text,
  created_at            timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_plasmids_code ON public.plasmids(code);

-- rnas table (linked to plasmids)
CREATE TABLE IF NOT EXISTS public.rnas (
  id_uuid           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code              text UNIQUE NOT NULL,
  name              text,
  source_plasmid_id uuid REFERENCES public.plasmids(id_uuid) ON DELETE SET NULL,
  created_by        text,
  notes             text,
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rnas_source_plasmid ON public.rnas(source_plasmid_id);

COMMIT;
