DO $$
BEGIN
  -- If legacy column exists, backfill and drop it
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'fish_seed_batches_map'
      AND column_name = 'fish_id'
  ) THEN
    UPDATE public.fish_seed_batches_map
       SET fish_uuid = COALESCE(fish_uuid, fish_id)
     WHERE fish_uuid IS NULL;

    -- Drop the legacy column to make replays idempotent
    BEGIN
      ALTER TABLE public.fish_seed_batches_map DROP COLUMN IF EXISTS fish_id;
    EXCEPTION WHEN undefined_column THEN
      -- no-op
      NULL;
    END;
  END IF;
END
$$;
