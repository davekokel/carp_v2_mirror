BEGIN;

-- Drop legacy/alias view that shadows fish_instances_v10.
-- Naming convention for views is v_*, and all modern code uses fish_instances_v10.

DROP VIEW IF EXISTS public.fish_instances;

COMMIT;
