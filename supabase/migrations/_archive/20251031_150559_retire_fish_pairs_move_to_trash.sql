DO $$
BEGIN
  -- keep quarantine schema available
  EXECUTE 'CREATE SCHEMA IF NOT EXISTS trash_carp';

  -- move the legacy conceptual pair table out of public (no shims)
  IF to_regclass('public.fish_pairs') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.fish_pairs SET SCHEMA trash_carp';
  END IF;
END $$;
