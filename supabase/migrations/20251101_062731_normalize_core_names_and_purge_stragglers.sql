DO $$
BEGIN
  -- quarantine schema exists
  EXECUTE 'CREATE SCHEMA IF NOT EXISTS trash_carp';

  -- 1) Canonical renames (only if target doesn't already exist)
  IF to_regclass('public.treatments') IS NULL
     AND to_regclass('public.clutch_materials') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.clutch_materials RENAME TO treatments';
  END IF;

  IF to_regclass('public.join_fish_tank_memberships') IS NULL
     AND to_regclass('public.fish_tank_memberships') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.fish_tank_memberships RENAME TO join_fish_tank_memberships';
  END IF;

  -- Standardize plasmid fusion join name
  IF to_regclass('public.join_plasmid_fusions') IS NULL
     AND to_regclass('public.plasmid_fusions') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.plasmid_fusions RENAME TO join_plasmid_fusions';
  END IF;
  -- If a stray join_plasmid_fusions AND plasmid_fusions both exist, prefer the canonical join_* and drop the duplicate table name to trash
  IF to_regclass('public.plasmid_fusions') IS NOT NULL
     AND to_regclass('public.join_plasmid_fusions') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.plasmid_fusions SET SCHEMA trash_carp';
  END IF;

  -- 2) Move non-core tables to trash_carp (only if present)
  IF to_regclass('public.containers') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.containers SET SCHEMA trash_carp';
  END IF;

  IF to_regclass('public.label_jobs') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.label_jobs SET SCHEMA trash_carp';
  END IF;

  IF to_regclass('public.label_items') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.label_items SET SCHEMA trash_carp';
  END IF;

  IF to_regclass('public.fish_year_counters') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.fish_year_counters SET SCHEMA trash_carp';
  END IF;

  IF to_regclass('public.transgene_allele_registry') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.transgene_allele_registry SET SCHEMA trash_carp';
  END IF;

  -- 3) Drop/Trash obvious accidents
  IF to_regclass('public.join_fish_tanks') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.join_fish_tanks SET SCHEMA trash_carp';
  END IF;
END
$$;

-- (Optional) quick inventory to verify:
-- SELECT n.nspname AS schema, COUNT(*) AS tables
-- FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
-- WHERE c.relkind IN ('r','p') AND n.nspname IN ('public','trash_carp')
-- GROUP BY 1 ORDER BY 1;
