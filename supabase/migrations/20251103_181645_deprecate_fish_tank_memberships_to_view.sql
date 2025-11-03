BEGIN;

-- If a VIEW exists, drop it first
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='fish_tank_memberships' AND c.relkind='v'
  ) THEN
    EXECUTE 'DROP VIEW public.fish_tank_memberships';
  END IF;
END$$;

-- If a TABLE exists, rename it to _legacy
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='fish_tank_memberships' AND c.relkind='r'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='fish_tank_memberships_legacy'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish_tank_memberships RENAME TO fish_tank_memberships_legacy';
  END IF;
END$$;

-- Recreate compat VIEW backed by join_fish_tanks
CREATE VIEW public.fish_tank_memberships AS
SELECT
  j.id,
  j.fish_id,
  j.tank_id,
  COALESCE(j.valid_from, j.since, now()) AS created_at,
  j.since,
  j.until
FROM public.join_fish_tanks j;

COMMIT;
