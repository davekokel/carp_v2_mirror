DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.fish'::regclass AND contype = 'p'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD PRIMARY KEY (id_uuid)';
  END IF;
END$$;

-- Add the FK after table exists (idempotent & safe)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'fk_fsbm_fish' AND conrelid = 'public.fish_seed_batches_map'::regclass
  ) THEN
    EXECUTE '
      ALTER TABLE public.fish_seed_batches_map
      ADD CONSTRAINT fk_fsbm_fish
      FOREIGN KEY (fish_id) REFERENCES public.fish(id_uuid) ON DELETE CASCADE NOT VALID';
    EXECUTE 'ALTER TABLE public.fish_seed_batches_map VALIDATE CONSTRAINT fk_fsbm_fish';
  END IF;
END$$;
