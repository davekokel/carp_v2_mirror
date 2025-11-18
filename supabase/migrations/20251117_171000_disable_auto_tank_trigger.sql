BEGIN;

-- Temporarily disable automatic tank assignment on fish insert.
-- The trigger still exists but does nothing; tank memberships
-- should be created explicitly by tank loaders / UI.
CREATE OR REPLACE FUNCTION public.trg_fish_instance_auto_tank()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  -- no-op: do not auto-create tank_memberships
  RETURN NEW;
END;
$$;

COMMIT;
