BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name   = 'construct_plasmids'
  ) THEN
    CREATE TABLE public.construct_plasmids (
      construct_id uuid PRIMARY KEY REFERENCES public.constructs(id) ON DELETE CASCADE,
      resistance   text,
      backbone     text,
      notes        text
    );
  END IF;
END $$;

COMMIT;
