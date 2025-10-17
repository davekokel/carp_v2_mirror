BEGIN;

-- Drop existing tank_code shape constraint if present
DO $$
DECLARE conname text;
BEGIN
  SELECT conname INTO conname
  FROM pg_constraint
  WHERE conrelid='public.containers'::regclass
    AND contype='c'
    AND conname='chk_tank_code_shape';
  IF conname IS NOT NULL THEN
    EXECUTE format('ALTER TABLE public.containers DROP CONSTRAINT %I', conname);
  END IF;
END $$;

-- Enforce only: TANK FSH-<FISH_CODE> #<n>   (no #0, case-insensitive A–Z, digits)
ALTER TABLE public.containers
  ADD CONSTRAINT chk_tank_code_shape
  CHECK (
    tank_code IS NULL
    OR tank_code ~ '^TANK FSH-[0-9A-Z]{2}[0-9A-Z]+ #[1-9][0-9]*$'
  );

-- Keep uniqueness on non-null codes
CREATE UNIQUE INDEX IF NOT EXISTS uq_containers_tank_code
  ON public.containers(tank_code)
  WHERE tank_code IS NOT NULL;

COMMIT;
