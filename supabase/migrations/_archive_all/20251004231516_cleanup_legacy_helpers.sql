-- Remove legacy helper(s) that can conflict with current baseline/migrations.
-- Idempotent: drops any function named _table_has regardless of schema/signature.

DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT n.nspname AS schemaname, p.oid::regprocedure AS regproc
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE p.proname = '_table_has'
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.regproc);
  END LOOP;
END $$;

-- Ensure helper schema exists before downstream creates (no-op if present)
CREATE SCHEMA IF NOT EXISTS util_mig;
