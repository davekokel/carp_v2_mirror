DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE t.typname = 'clutch_plan_status' AND n.nspname = 'public'
  ) THEN
    CREATE TYPE public.clutch_plan_status AS ENUM ('draft','ready','scheduled','closed');
  END IF;
END $$;
