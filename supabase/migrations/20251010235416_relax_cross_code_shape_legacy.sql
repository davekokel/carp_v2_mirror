-- Allow legacy CR-... codes as well as CROSS-... (case-insensitive optional)
ALTER TABLE public.crosses
  DROP CONSTRAINT IF EXISTS chk_cross_code_shape;

-- Keep it NOT VALID to avoid blocking if any other odd legacy rows exist
ALTER TABLE public.crosses
  ADD CONSTRAINT chk_cross_code_shape
  CHECK (
    cross_code IS NULL
    OR cross_code ~ '^(CROSS|CR)-[0-9A-Z]{2}[0-9A-Z]{4,}$'
  ) NOT VALID;

-- Best-effort validate (won’t fail the migration if some rows still don’t match)
DO $$
BEGIN
  BEGIN
    ALTER TABLE public.crosses VALIDATE CONSTRAINT chk_cross_code_shape;
  EXCEPTION WHEN others THEN
    -- leave as NOT VALID; new rows are still guarded; we can clean & validate later
    NULL;
  END;
END$$;
