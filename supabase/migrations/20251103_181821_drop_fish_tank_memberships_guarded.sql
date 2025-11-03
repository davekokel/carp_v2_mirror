BEGIN;

-- 1) Drop legacy table if present
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='fish_tank_memberships_legacy'
  ) THEN
    EXECUTE 'DROP TABLE public.fish_tank_memberships_legacy';
  END IF;
END$$;

-- 2) Drop the VIEW if it exists and has no dependents (or skip if it does)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='fish_tank_memberships' AND c.relkind='v'
  ) THEN
    BEGIN
      EXECUTE 'DROP VIEW public.fish_tank_memberships';
    EXCEPTION WHEN dependent_objects_still_exist THEN
      RAISE NOTICE 'Not dropping view public.fish_tank_memberships; dependent objects exist';
    END;
  END IF;
END$$;

COMMIT;
