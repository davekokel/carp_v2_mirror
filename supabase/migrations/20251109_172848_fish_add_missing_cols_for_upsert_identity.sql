BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Add any columns the upsert expects, only if missing
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='description'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD COLUMN description text';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='genetic_background'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD COLUMN genetic_background text';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='in_breeding_stage'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD COLUMN in_breeding_stage text';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='identity_key'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD COLUMN identity_key text';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='identity_hash'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD COLUMN identity_hash text';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='created_by'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD COLUMN created_by text';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='created_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD COLUMN created_at timestamptz DEFAULT now()';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='nickname'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD COLUMN nickname text';
  END IF;
END$$;

-- Helpful indexes/constraints (guarded)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='fish' AND indexname='idx_fish_identity_hash'
  ) THEN
    EXECUTE 'CREATE INDEX idx_fish_identity_hash ON public.fish(identity_hash)';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='fish' AND indexname='idx_fish_identity_key'
  ) THEN
    EXECUTE 'CREATE INDEX idx_fish_identity_key ON public.fish(identity_key)';
  END IF;

  -- Ensure fish_code unique if not already
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='fish' AND constraint_type='UNIQUE'
      AND constraint_name='uq_fish_fish_code'
  ) THEN
    -- guard: only add if no duplicate fish_code exists
    IF NOT EXISTS (
      SELECT fish_code FROM public.fish
      GROUP BY fish_code HAVING COUNT(*) > 1
    ) THEN
      EXECUTE 'ALTER TABLE public.fish ADD CONSTRAINT uq_fish_fish_code UNIQUE (fish_code)';
    END IF;
  END IF;
END$$;

COMMIT;
