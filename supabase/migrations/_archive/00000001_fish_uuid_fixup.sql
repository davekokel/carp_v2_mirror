BEGIN;

-- ─────────────────────────────────────────────
-- 🧱 Normalize fish table to use fish_uuid PK
-- ─────────────────────────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish'
      AND column_name='id'
  ) THEN
    ALTER TABLE public.fish RENAME COLUMN id TO fish_uuid;
  END IF;
END $$;

ALTER TABLE public.fish
  ALTER COLUMN fish_uuid SET DEFAULT gen_random_uuid();

DO $$
DECLARE pk text;
BEGIN
  SELECT constraint_name INTO pk
  FROM information_schema.table_constraints
  WHERE table_schema='public'
    AND table_name='fish'
    AND constraint_type='PRIMARY KEY';
  IF pk IS NOT NULL THEN
    EXECUTE format('ALTER TABLE public.fish DROP CONSTRAINT %I CASCADE', pk);
  END IF;
END $$;

ALTER TABLE public.fish ADD PRIMARY KEY (fish_uuid);

COMMIT;

-- ─────────────────────────────────────────────
-- 🧱 Normalize fish_tank_memberships (UUIDs)
-- ─────────────────────────────────────────────
DO $$
BEGIN
  -- fish_id → fish_uuid
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish_tank_memberships'
      AND column_name='fish_id'
  ) THEN
    ALTER TABLE public.fish_tank_memberships RENAME COLUMN fish_id TO fish_uuid;
  END IF;

  -- tank_id → tank_uuid
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish_tank_memberships'
      AND column_name='tank_id'
  ) THEN
    ALTER TABLE public.fish_tank_memberships RENAME COLUMN tank_id TO tank_uuid;
  END IF;

  -- container_id → tank_uuid (only if tank_uuid doesn't already exist)
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish_tank_memberships'
      AND column_name='container_id'
  )
  AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish_tank_memberships'
      AND column_name='tank_uuid'
  ) THEN
    ALTER TABLE public.fish_tank_memberships RENAME COLUMN container_id TO tank_uuid;
  END IF;

  -- joined_at → started_at (no DROP to avoid breaking dependent views)
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish_tank_memberships'
      AND column_name='joined_at'
  )
  AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish_tank_memberships'
      AND column_name='started_at'
  ) THEN
    ALTER TABLE public.fish_tank_memberships RENAME COLUMN joined_at TO started_at;
  END IF;

  -- add ended_at if missing
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish_tank_memberships'
      AND column_name='ended_at'
  ) THEN
    ALTER TABLE public.fish_tank_memberships ADD COLUMN ended_at timestamptz;
  END IF;
END $$;

-- ─────────────────────────────────────────────
-- Normalize fish_transgene_alleles → use fish_uuid
-- ─────────────────────────────────────────────
DO $$
DECLARE has_old_col boolean;
DECLARE has_named_fk boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish_transgene_alleles'
      AND column_name='fish_id'
  ) INTO has_old_col;

  IF has_old_col THEN
    ALTER TABLE public.fish_transgene_alleles RENAME COLUMN fish_id TO fish_uuid;
  END IF;

  -- add named FK only if it's not already present
  SELECT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname='public'
      AND t.relname='fish_transgene_alleles'
      AND c.conname='fk_fish_transgene_alleles_fish_uuid'
  ) INTO has_named_fk;

  IF NOT has_named_fk THEN
    EXECUTE 'ALTER TABLE public.fish_transgene_alleles
             ADD CONSTRAINT fk_fish_transgene_alleles_fish_uuid
             FOREIGN KEY (fish_uuid) REFERENCES public.fish(fish_uuid) ON DELETE CASCADE';
  END IF;
END $$;