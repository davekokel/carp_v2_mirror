BEGIN;

DO $$
BEGIN
  -- rename id → fish_uuid if still present
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish'
      AND column_name='id'
  ) THEN
    ALTER TABLE public.fish RENAME COLUMN id TO fish_uuid;
  END IF;
END$$;

-- ensure default and primary key are set
ALTER TABLE public.fish
  ALTER COLUMN fish_uuid SET DEFAULT gen_random_uuid();

DO $$
DECLARE
  pk_name text;
BEGIN
  SELECT constraint_name INTO pk_name
  FROM information_schema.table_constraints
  WHERE table_schema='public'
    AND table_name='fish'
    AND constraint_type='PRIMARY KEY';

  IF pk_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE public.fish DROP CONSTRAINT %I CASCADE', pk_name);
  END IF;
END$$;

ALTER TABLE public.fish ADD PRIMARY KEY (fish_uuid);

COMMIT;
