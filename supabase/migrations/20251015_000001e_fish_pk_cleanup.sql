DO $$
DECLARE pk text;
BEGIN
  SELECT conname INTO pk
  FROM pg_constraint
  WHERE conrelid='public.fish'::regclass AND contype='p'
  LIMIT 1;
  IF pk IS NOT NULL THEN
    EXECUTE format('ALTER TABLE public.fish DROP CONSTRAINT %I', pk);
  END IF;
END$$;
