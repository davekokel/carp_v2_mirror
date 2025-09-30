-- 2025-10-01_wide_links.sql
-- Idempotent: only creates link tables if they don't already exist.
-- Assumes these already exist:
--   public.fish(id uuid PK)
--   public.plasmids(code text PK)
--   public.rnas(code text PK)
--   public.dyes(name text PK)
--   public.fluors(name text PK)

-- ========= Plasmids ⇄ Fish ===============================================
CREATE TABLE IF NOT EXISTS public.fish_plasmids (
  fish_id       uuid REFERENCES public.fish(id) ON DELETE CASCADE,
  plasmid_code  text REFERENCES public.plasmids(code) ON DELETE RESTRICT,
  PRIMARY KEY (fish_id, plasmid_code)
);

-- ========= RNAs ⇄ Fish ====================================================
CREATE TABLE IF NOT EXISTS public.fish_rnas (
  fish_id   uuid REFERENCES public.fish(id) ON DELETE CASCADE,
  rna_code  text REFERENCES public.rnas(code) ON DELETE RESTRICT,
  PRIMARY KEY (fish_id, rna_code)
);

-- ========= Dyes ⇄ Fish ====================================================
CREATE TABLE IF NOT EXISTS public.fish_dyes (
  fish_id   uuid REFERENCES public.fish(id) ON DELETE CASCADE,
  dye_name  text REFERENCES public.dyes(name) ON DELETE RESTRICT,
  PRIMARY KEY (fish_id, dye_name)
);

-- ========= Fluors ⇄ Fish ==================================================
CREATE TABLE IF NOT EXISTS public.fish_fluors (
  fish_id     uuid REFERENCES public.fish(id) ON DELETE CASCADE,
  fluor_name  text REFERENCES public.fluors(name) ON DELETE RESTRICT,
  PRIMARY KEY (fish_id, fluor_name)
);

-- (Optional but cheap) add supporting indexes only if they don't exist.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                 WHERE c.relkind='i' AND c.relname='idx_fish_plasmids_plasmid_code' AND n.nspname='public') THEN
    CREATE INDEX idx_fish_plasmids_plasmid_code ON public.fish_plasmids(plasmid_code);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                 WHERE c.relkind='i' AND c.relname='idx_fish_rnas_rna_code' AND n.nspname='public') THEN
    CREATE INDEX idx_fish_rnas_rna_code ON public.fish_rnas(rna_code);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                 WHERE c.relkind='i' AND c.relname='idx_fish_dyes_dye_name' AND n.nspname='public') THEN
    CREATE INDEX idx_fish_dyes_dye_name ON public.fish_dyes(dye_name);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                 WHERE c.relkind='i' AND c.relname='idx_fish_fluors_fluor_name' AND n.nspname='public') THEN
    CREATE INDEX idx_fish_fluors_fluor_name ON public.fish_fluors(fluor_name);
  END IF;
END $$;