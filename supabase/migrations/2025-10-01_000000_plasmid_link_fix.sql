

-- fish <-> plasmids junction (idempotent, matches current schema)

-- Ensure the target tables exist (no-ops if they already do)
CREATE TABLE IF NOT EXISTS public.fish (
  id uuid PRIMARY KEY
);

-- plasmids already exists with:
--   id_uuid uuid PRIMARY KEY
--   plasmid_code text UNIQUE
--   name text
-- …and other columns.

-- Create junction using the real PKs: fish.id and plasmids.id_uuid
CREATE TABLE IF NOT EXISTS public.fish_plasmids (
  fish_id     uuid NOT NULL REFERENCES public.fish(id)        ON DELETE CASCADE,
  plasmid_id  uuid NOT NULL REFERENCES public.plasmids(id_uuid) ON DELETE RESTRICT,
  PRIMARY KEY (fish_id, plasmid_id)
);

-- Helpful index for reverse lookups (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relname = 'idx_fish_plasmids_plasmid_id'
      AND n.nspname = 'public'
  ) THEN
    CREATE INDEX idx_fish_plasmids_plasmid_id ON public.fish_plasmids(plasmid_id);
  END IF;
END $$;