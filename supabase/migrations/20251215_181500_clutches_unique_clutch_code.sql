BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname='public'
      AND t.relname='clutches'
      AND c.contype='u'
      AND c.conname='clutches_clutch_code_uniq'
  ) THEN
    ALTER TABLE public.clutches
    ADD CONSTRAINT clutches_clutch_code_uniq UNIQUE (clutch_code);
  END IF;
END $$;

COMMIT;
