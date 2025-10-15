-- Make local Postgres tolerant of Supabase-specific assumptions.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
    CREATE ROLE authenticated;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
    CREATE ROLE anon;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN
    CREATE ROLE service_role;
  END IF;
END
$$ LANGUAGE plpgsql;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
DO 28762
BEGIN
  PERFORM set_config('statement_timeout','0', true);
EXCEPTION WHEN undefined_object THEN
  NULL;
END
$$ LANGUAGE plpgsql;
DO 28762
BEGIN
  PERFORM set_config('transaction_timeout','0', true);
EXCEPTION WHEN undefined_object THEN
  NULL;
END
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.safe_drop_view(_schema text, _name text)
RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_views
    WHERE schemaname = _schema AND viewname = _name
  ) THEN
    EXECUTE format('DROP VIEW %I.%I CASCADE', _schema, _name);
  END IF;
END$$;
