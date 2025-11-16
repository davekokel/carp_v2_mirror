BEGIN;

CREATE TABLE IF NOT EXISTS public.legacy_injected_plasmids_map (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  injected_plasmid  text NOT NULL,
  plasmid_base_code text NOT NULL,
  CONSTRAINT legacy_injected_plasmids_map_unique
    UNIQUE (injected_plasmid)
);

CREATE INDEX IF NOT EXISTS idx_legacy_injected_plasmids_map_name
  ON public.legacy_injected_plasmids_map (injected_plasmid);

CREATE TABLE IF NOT EXISTS public.legacy_injected_rnas_map (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  injected_rna      text NOT NULL,
  plasmid_base_code text NOT NULL,
  CONSTRAINT legacy_injected_rnas_map_unique
    UNIQUE (injected_rna)
);

CREATE INDEX IF NOT EXISTS idx_legacy_injected_rnas_map_name
  ON public.legacy_injected_rnas_map (injected_rna);

COMMIT;
