-- Remove legacy requirement that tank_pairs.fish_pair_code must be non-null
-- and prevent duplicates via (mother_tank_id, father_tank_id, concept_id)

DO $$
BEGIN
  -- Drop the trigger if present
  IF EXISTS (
    SELECT 1
    FROM pg_trigger t
    JOIN pg_class c ON c.oid=t.tgrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='tank_pairs'
      AND t.tgname='trg_tank_pairs_require_fp'
  ) THEN
    EXECUTE 'DROP TRIGGER trg_tank_pairs_require_fp ON public.tank_pairs';
  END IF;

  -- Drop the trigger function if it exists (name based on error message)
  IF EXISTS (
    SELECT 1
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname='public' AND p.proname='trg_tank_pairs_require_fp'
  ) THEN
    EXECUTE 'DROP FUNCTION public.trg_tank_pairs_require_fp()';
  END IF;

  -- Make fish_pair_code nullable if it's NOT NULL
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs'
      AND column_name='fish_pair_code' AND is_nullable='NO'
  ) THEN
    EXECUTE 'ALTER TABLE public.tank_pairs ALTER COLUMN fish_pair_code DROP NOT NULL';
  END IF;

  -- Add a uniqueness constraint to prevent duplicate physical pairings
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='uq_tank_pairs_mom_dad_concept'
  ) THEN
    -- mother/father column names vary; try common variants
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='tank_pairs'
        AND column_name='mother_tank_id'
    ) AND EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='tank_pairs'
        AND column_name='father_tank_id'
    ) THEN
      EXECUTE 'ALTER TABLE public.tank_pairs
               ADD CONSTRAINT uq_tank_pairs_mom_dad_concept
               UNIQUE (mother_tank_id, father_tank_id, concept_id)';
    ELSIF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='tank_pairs'
        AND column_name='tank_id_mother'
    ) AND EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='tank_pairs'
        AND column_name='tank_id_father'
    ) THEN
      EXECUTE 'ALTER TABLE public.tank_pairs
               ADD CONSTRAINT uq_tank_pairs_mom_dad_concept
               UNIQUE (tank_id_mother, tank_id_father, concept_id)';
    END IF;
  END IF;
END $$;
