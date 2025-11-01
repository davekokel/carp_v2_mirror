DO $$
BEGIN
  -- Move from trash -> public only if public doesn't already have it; if both exist, drop trash copy.
  IF to_regclass('public.fluors') IS NULL AND to_regclass('trash_carp.fluors') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE trash_carp.fluors SET SCHEMA public';
  ELSIF to_regclass('public.fluors') IS NOT NULL AND to_regclass('trash_carp.fluors') IS NOT NULL THEN
    EXECUTE 'DROP TABLE trash_carp.fluors CASCADE';
  END IF;

  IF to_regclass('public.tags') IS NULL AND to_regclass('trash_carp.tags') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE trash_carp.tags SET SCHEMA public';
  ELSIF to_regclass('public.tags') IS NOT NULL AND to_regclass('trash_carp.tags') IS NOT NULL THEN
    EXECUTE 'DROP TABLE trash_carp.tags CASCADE';
  END IF;

  IF to_regclass('public.fusions') IS NULL AND to_regclass('trash_carp.fusions') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE trash_carp.fusions SET SCHEMA public';
  ELSIF to_regclass('public.fusions') IS NOT NULL AND to_regclass('trash_carp.fusions') IS NOT NULL THEN
    EXECUTE 'DROP TABLE trash_carp.fusions CASCADE';
  END IF;

  IF to_regclass('public.plasmid_fusions') IS NULL AND to_regclass('trash_carp.plasmid_fusions') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE trash_carp.plasmid_fusions SET SCHEMA public';
  ELSIF to_regclass('public.plasmid_fusions') IS NOT NULL AND to_regclass('trash_carp.plasmid_fusions') IS NOT NULL THEN
    EXECUTE 'DROP TABLE trash_carp.plasmid_fusions CASCADE';
  END IF;
END $$;

-- Create minimal schemas if still missing
CREATE TABLE IF NOT EXISTS public.fluors (
  fluor_code text PRIMARY KEY,
  fluor_name text NOT NULL
);

CREATE TABLE IF NOT EXISTS public.tags (
  tag_code text PRIMARY KEY,
  tag_name text NOT NULL
);

CREATE TABLE IF NOT EXISTS public.fusions (
  fusion_code text PRIMARY KEY,
  fusion_name text NOT NULL,
  fluor_code  text NOT NULL REFERENCES public.fluors(fluor_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  tag_code    text NULL REFERENCES public.tags(tag_code)        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_fusions_fluor_code ON public.fusions(fluor_code);
CREATE INDEX IF NOT EXISTS idx_fusions_tag_code   ON public.fusions(tag_code);

CREATE TABLE IF NOT EXISTS public.plasmid_fusions (
  plasmid_code text NOT NULL REFERENCES public.plasmids(code) ON UPDATE CASCADE ON DELETE CASCADE,
  fusion_code  text NOT NULL REFERENCES public.fusions(fusion_code) ON UPDATE CASCADE ON DELETE CASCADE,
  position_in_plasmid int NULL,
  PRIMARY KEY (plasmid_code, fusion_code)
);

CREATE INDEX IF NOT EXISTS idx_plasmid_fusions_fusion ON public.plasmid_fusions(fusion_code);
