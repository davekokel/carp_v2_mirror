DO $$
BEGIN
IF NOT EXISTS (
  SELECT 1
  FROM pg_type t
  JOIN pg_namespace n ON n.oid=t.typnamespace
  WHERE t.typname='container_status' AND n.nspname='public'
) THEN
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace n ON n.oid=t.typnamespace
    WHERE t.typname='container_status' AND n.nspname='public'
  ) THEN
    CREATE TYPE public.container_status AS ENUM ('planned', 'active', 'to_kill', 'retired');
  END IF;
END
$$ LANGUAGE plpgsql;
END IF;
END$$;
DO $$
BEGIN
IF NOT EXISTS (
  SELECT 1
  FROM pg_type t
  JOIN pg_namespace n ON n.oid=t.typnamespace
  WHERE t.typname='cross_plan_status' AND n.nspname='public'
) THEN
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace n ON n.oid=t.typnamespace
    WHERE t.typname='cross_plan_status' AND n.nspname='public'
  ) THEN
    CREATE TYPE public.cross_plan_status AS ENUM ('planned', 'canceled', 'executed');
  END IF;
END
$$ LANGUAGE plpgsql;
END IF;
END$$;
