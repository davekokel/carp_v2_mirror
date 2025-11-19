BEGIN;

----------------------------------------------------------------------
-- v8: Make tanks.fish_id canonical and turn tank_memberships into a VIEW
--
-- Canonical relationship:
--   fish_instance.id ← tanks.fish_id
--
-- Strategy:
--   1) Drop any legacy tank_memberships TABLE.
--   2) Recreate tank_memberships as a VIEW over tanks for compatibility.
----------------------------------------------------------------------

-- 1. Drop legacy table if it exists
DROP TABLE IF EXISTS public.tank_memberships CASCADE;

-- 2. Drop any existing view with that name
DROP VIEW IF EXISTS public.tank_memberships CASCADE;

-- 3. Recreate as view based on tanks
CREATE VIEW public.tank_memberships AS
SELECT
  t.id        AS tank_id,
  t.fish_id   AS fish_id,
  t.created_at AS started_at,
  NULL::timestamptz AS ended_at,
  t.status,
  t.location,
  t.notes
FROM public.tanks t
WHERE t.fish_id IS NOT NULL;

COMMIT;
