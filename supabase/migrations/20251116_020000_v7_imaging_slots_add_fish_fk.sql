BEGIN;

-- Add fish_id column to imaging_slots if it doesn't exist
ALTER TABLE public.imaging_slots
  ADD COLUMN IF NOT EXISTS fish_id uuid;

-- Add foreign key from imaging_slots.fish_id → fish_instance.id
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.imaging_slots'::regclass
      AND conname  = 'fk_imaging_slots_fish'
  ) THEN
    ALTER TABLE public.imaging_slots
      ADD CONSTRAINT fk_imaging_slots_fish
      FOREIGN KEY (fish_id)
      REFERENCES public.fish_instance(id)
      ON UPDATE CASCADE
      ON DELETE SET NULL;
  END IF;
END$$;

-- Helpful index
CREATE INDEX IF NOT EXISTS idx_imaging_slots_fish_id
  ON public.imaging_slots (fish_id);

COMMIT;
