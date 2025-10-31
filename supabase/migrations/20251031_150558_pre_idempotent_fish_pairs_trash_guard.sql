DO $$
BEGIN
  -- Ensure target schema exists
  EXECUTE 'CREATE SCHEMA IF NOT EXISTS trash_carp';

  IF to_regclass('public.fish_pairs') IS NOT NULL
     AND to_regclass('trash_carp.fish_pairs') IS NOT NULL THEN
    -- Keep the retired copy; drop the public duplicate to avoid later ALTER … SET SCHEMA collision
    EXECUTE 'DROP TABLE public.fish_pairs CASCADE';
  ELSIF to_regclass('public.fish_pairs') IS NOT NULL
     AND to_regclass('trash_carp.fish_pairs') IS NULL THEN
    -- If only public exists, retire it now so later "retire" migration becomes a no-op
    EXECUTE 'ALTER TABLE public.fish_pairs SET SCHEMA trash_carp';
  END IF;
END $$;
