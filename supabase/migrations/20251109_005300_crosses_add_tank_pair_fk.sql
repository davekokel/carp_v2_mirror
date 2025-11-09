BEGIN;

-- Add column only if missing
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='crosses' AND column_name='tank_pair_id'
  ) THEN
    ALTER TABLE public.crosses ADD COLUMN tank_pair_id uuid;
  END IF;
END$$;

-- Helpful index
CREATE INDEX IF NOT EXISTS idx_crosses_tank_pair_id ON public.crosses(tank_pair_id);

-- FK (deferrable, not validated yet)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.crosses'::regclass
      AND conname='fk_crosses_tank_pair_id__tank_pairs_id'
  ) THEN
    ALTER TABLE public.crosses
      ADD CONSTRAINT fk_crosses_tank_pair_id__tank_pairs_id
      FOREIGN KEY (tank_pair_id) REFERENCES public.tank_pairs(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
END$$;

COMMIT;
