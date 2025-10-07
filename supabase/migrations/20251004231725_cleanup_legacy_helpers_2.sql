-- Drop legacy helper functions that can collide with the baseline.
-- Idempotent: removes any function named _to_base36 (or related) regardless of schema/signature.

DO $$
DECLARE r record;
BEGIN
  -- drop any _to_base36
  FOR r IN
    SELECT p.oid::regprocedure AS regproc
    FROM pg_proc p
    WHERE p.proname = '_to_base36'
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.regproc);
  END LOOP;

  -- (optional) drop any _from_base36 if you had one historically
  FOR r IN
    SELECT p.oid::regprocedure AS regproc
    FROM pg_proc p
    WHERE p.proname = '_from_base36'
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.regproc);
  END LOOP;
END $$;

-- Ensure helper schema exists before downstream creates (no-op if present)
CREATE SCHEMA IF NOT EXISTS util_mig;
