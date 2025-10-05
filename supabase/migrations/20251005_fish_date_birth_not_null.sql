-- Enforce mandatory birth dates for fish
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.fish WHERE date_birth IS NULL) THEN
    RAISE EXCEPTION 'Cannot SET NOT NULL: public.fish has rows with date_birth IS NULL';
  END IF;
END $$;

ALTER TABLE public.fish
  ALTER COLUMN date_birth SET NOT NULL;
