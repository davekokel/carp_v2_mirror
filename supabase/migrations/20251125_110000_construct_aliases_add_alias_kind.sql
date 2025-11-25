BEGIN;

-- ensure construct_aliases exists (for safety)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name   = 'construct_aliases'
  ) THEN
    CREATE TABLE public.construct_aliases (
      id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
      construct_id uuid NOT NULL REFERENCES public.constructs(id) ON DELETE CASCADE,
      alias        text NOT NULL UNIQUE,
      created_at   timestamptz NOT NULL DEFAULT now()
    );
  END IF;
END $$;

-- add alias_kind if missing
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'construct_aliases'
      AND column_name  = 'alias_kind'
  ) THEN
    ALTER TABLE public.construct_aliases
      ADD COLUMN alias_kind text;
  END IF;
END $$;

COMMIT;
