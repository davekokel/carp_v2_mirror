DO $$
BEGIN
  -- ensure quarantine schema
  EXECUTE 'CREATE SCHEMA IF NOT EXISTS trash_carp';

  -- 1) clutch_materials → treatments (or move to trash if treatments already exists)
  IF to_regclass('public.clutch_materials') IS NOT NULL THEN
    IF to_regclass('public.treatments') IS NULL THEN
      EXECUTE 'ALTER TABLE public.clutch_materials RENAME TO treatments';
    ELSE
      EXECUTE 'ALTER TABLE public.clutch_materials SET SCHEMA trash_carp';
    END IF;
  END IF;

  -- 2) fish_tank_memberships → join_fish_tank_memberships (or move to trash if join_* already exists)
  IF to_regclass('public.fish_tank_memberships') IS NOT NULL THEN
    IF to_regclass('public.join_fish_tank_memberships') IS NULL THEN
      EXECUTE 'ALTER TABLE public.fish_tank_memberships RENAME TO join_fish_tank_memberships';
    ELSE
      EXECUTE 'ALTER TABLE public.fish_tank_memberships SET SCHEMA trash_carp';
    END IF;
  END IF;

  -- 3) join_fish_tanks (accidental) → trash
  IF to_regclass('public.join_fish_tanks') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.join_fish_tanks SET SCHEMA trash_carp';
  END IF;

  -- 4) containers → trash (not part of the finalized core)
  IF to_regclass('public.containers') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.containers SET SCHEMA trash_carp';
  END IF;

  -- 5) label_jobs / label_items → trash
  IF to_regclass('public.label_jobs') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.label_jobs SET SCHEMA trash_carp';
  END IF;
  IF to_regclass('public.label_items') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.label_items SET SCHEMA trash_carp';
  END IF;

  -- 6) fish_year_counters → trash
  IF to_regclass('public.fish_year_counters') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.fish_year_counters SET SCHEMA trash_carp';
  END IF;

  -- 7) transgene_allele_registry → trash (redundant in v2)
  IF to_regclass('public.transgene_allele_registry') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.transgene_allele_registry SET SCHEMA trash_carp';
  END IF;
END
$$;
